import arc.*;
import arc.backend.headless.HeadlessApplication;
import arc.files.Fi;
import arc.math.Mathf;
import arc.math.geom.Point2;
import arc.mock.MockGraphics;
import arc.util.*;
import arc.util.serialization.Jval;
import mindustry.*;
import mindustry.content.*;
import mindustry.core.*;
import mindustry.core.GameState.State;
import mindustry.ctype.ContentType;
import mindustry.game.Team;
import mindustry.gen.*;
import mindustry.net.Net;
import mindustry.type.*;
import mindustry.world.*;
import mindustry.world.blocks.power.PowerNode;
import mindustry.world.blocks.power.PowerGenerator;
import mindustry.world.blocks.power.ConsumeGenerator;
import mindustry.world.blocks.production.*;
import mindustry.world.consumers.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import static mindustry.Vars.*;

/** Drives unmodified, official Mindustry game logic at a fixed 60 ticks/second. */
public class FactoryRunner {
    static String output;
    static final String[] allowed = {"conveyor", "titanium-conveyor", "router", "junction", "sorter",
        "inverted-sorter", "overflow-gate", "underflow-gate", "mechanical-drill", "pneumatic-drill",
        "graphite-press", "silicon-smelter", "solar-panel", "power-node", "battery",
        "mechanical-pump", "rotary-pump", "conduit", "pulse-conduit", "liquid-router", "liquid-junction",
        "liquid-container", "steam-generator", "combustion-generator", "cultivator", "spore-press",
        "plastanium-compressor", "pyratite-mixer", "blast-mixer", "surge-smelter"};
    static Block block(String name) {
        Block b = content.getByName(ContentType.block, name);
        if (b == null) throw new IllegalArgumentException("Unknown block: " + name);
        return b;
    }
    static int cost(Block b) {
        int n=0; for (ItemStack r:b.requirements) n+=r.amount; return n;
    }
    static Jval inventory(Building b) {
        Jval r=Jval.newObject();
        if(b.items != null) for(Item i:content.items()) if(b.items.get(i)>0) r.put(i.name,b.items.get(i));
        return r;
    }
    static Jval snapshot(int tick, List<Building> buildings, Building core) {
        Jval a=Jval.newArray();
        for(Building b:buildings) {
            Jval row=Jval.newObject().put("x",b.tileX()).put("y",b.tileY()).put("block",b.block.name)
                .put("size",b.block.size).put("rotation",b.rotation).put("items",inventory(b))
                .put("efficiency",b.efficiency);
            if(b.liquids!=null) {
                Jval liquids=Jval.newObject();
                for(Liquid l:content.liquids()) if(b.liquids.get(l)>0) liquids.put(l.name,b.liquids.get(l));
                row.put("liquids",liquids);
            }
            if(b.power!=null) {
                row.put("power",b.power.status);
                row.put("grid",Jval.newObject().put("produced_per_tick",b.power.graph.getLastPowerProduced())
                    .put("needed_per_tick",b.power.graph.getLastPowerNeeded()).put("stored",b.power.graph.getLastPowerStored()));
                if(b.block instanceof PowerNode){
                    List<Integer> positions=new ArrayList<>();
                    for(int link:b.power.links.toArray())positions.add(link);
                    Collections.sort(positions);
                    Jval links=Jval.newArray();
                    for(int link:positions)links.add(Jval.newArray().add(Point2.x(link)).add(Point2.y(link)));
                    row.put("links",links);
                }
            }
            a.add(row);
        }
        return Jval.newObject().put("tick",tick).put("core",inventory(core)).put("buildings",a);
    }
    static void canonicalizeNeighbors(List<Building> buildings, Building core) {
        // Native updateProximity() copies an ObjectSet<Building>. Its identity
        // hashes are not controlled by Mathf.rand, and dump/offload uses that
        // sequence. Define this part of the initial state after all placement
        // and configuration callbacks, before any simulated tick.
        // This task has no construction or destruction during the simulation.
        Comparator<Building> order=Comparator.comparingInt((Building b)->b.tileY())
            .thenComparingInt(b->b.tileX());
        for(Building b:buildings) b.proximity.sort(order);
        core.proximity.sort(order);
    }
    static void initEngine(Path scratch) {
        Log.logger=(level,text)->System.err.println(text);
        headless=true; loadLocales=false;
        Core.settings.setDataDirectory(new Fi(scratch.toFile()));
        Core.settings.setAutosave(false);
        Core.graphics=new MockGraphics(){@Override public float getDeltaTime(){return 1f/60f;}};
        platform=new Platform(){};
        net=new Net(null);
        Vars.init();
        content.createBaseContent();
        logic=new Logic();
        netServer=new NetServer();
        content.init();
        Time.setDeltaProvider(()->1f);
    }
    static Jval catalog() {
        Jval list=Jval.newArray();
        for(String name:allowed){
            Block b=block(name); Jval req=Jval.newObject();
            for(ItemStack r:b.requirements) req.put(r.item.name,r.amount);
            Jval row=Jval.newObject().put("name",name).put("size",b.size).put("cost",cost(b))
                .put("requirements",req).put("has_power",b.hasPower).put("item_capacity",b.itemCapacity)
                .put("liquid_capacity",b.liquidCapacity);
            Jval inputs=Jval.newArray();
            for(Consume consumer:b.consumers){
                Jval input=Jval.newObject().put("type",consumer.getClass().getSimpleName())
                    .put("optional",consumer.optional).put("booster",consumer.booster);
                if(consumer instanceof ConsumeItems ci){
                    Jval items=Jval.newObject();for(ItemStack stack:ci.items)items.put(stack.item.name,stack.amount);
                    input.put("items_per_craft",items);
                }
                if(consumer instanceof ConsumeLiquid cl)input.put("liquid",cl.liquid.name).put("amount_per_tick",cl.amount);
                if(consumer instanceof ConsumePower cp)input.put("power_per_tick",cp.usage).put("buffer_capacity",cp.capacity);
                if(consumer instanceof ConsumeItemFlammable cf){
                    Jval fuels=Jval.newObject();for(Item item:content.items())if(cf.filter.get(item))fuels.put(item.name,cf.itemEfficiencyMultiplier(item));
                    input.put("fuel_efficiencies",fuels);
                }
                inputs.add(input);
            }
            row.put("consumers",inputs);
            if(b instanceof GenericCrafter gc){
                row.put("craft_ticks",gc.craftTime);
                Jval items=Jval.newObject(),liquids=Jval.newObject();
                if(gc.outputItems!=null)for(ItemStack stack:gc.outputItems)items.put(stack.item.name,stack.amount);
                if(gc.outputLiquids!=null)for(LiquidStack stack:gc.outputLiquids)liquids.put(stack.liquid.name,stack.amount);
                row.put("output_items_per_craft",items).put("output_liquids_per_tick",liquids);
            }
            if(b instanceof Pump pump)row.put("pump_per_tick_per_tile",pump.pumpAmount);
            if(b instanceof Drill drill)row.put("drill_tier",drill.tier).put("base_drill_ticks",drill.drillTime);
            if(b instanceof PowerGenerator pg)row.put("base_power_production_per_tick",pg.powerProduction);
            if(b instanceof ConsumeGenerator cg)row.put("base_fuel_duration_ticks",cg.itemDuration);
            list.add(row);
        }
        return Jval.newObject().put("version",Version.buildString()).put("blocks",list);
    }
    static Jval simulate(Jval input) {
        Jval task=input.get("task"), blueprint=input.get("blueprint");
        int width=task.getInt("width",0),height=task.getInt("height",0),ticks=task.getInt("ticks",0);
        if(width<8||height<8||width>128||height>128||ticks<1||ticks>36000) throw new IllegalArgumentException("Invalid trusted task size");
        logic.reset();
        Time.clear(); Time.setInternalTime(0); Time.time=0;Time.globalTime=0;Time.delta=1;
        Mathf.rand.setSeed(task.getLong("seed",1));
        state.rules.waves=false;state.rules.waveTimer=false;state.rules.canGameOver=false;
        state.rules.lighting=false;state.rules.fog=false;state.rules.infiniteResources=false;
        state.rules.coreIncinerates=false;
        // This is a fixed factory production task: native rules disable hazards
        // that could otherwise change topology when an explosive fuel is supplied.
        state.rules.reactorExplosions=false;state.rules.fire=false;
        state.rules.defaultTeam=Team.sharded;
        world.beginMapLoad(); world.resize(width,height);
        for(int y=0;y<height;y++) for(int x=0;x<width;x++) world.tiles.set(x,y,new Tile(x,y,Blocks.stone,Blocks.air,Blocks.air));
        for(Jval p:task.get("patches").asArray()) {
            int x0=p.getInt("x",0),y0=p.getInt("y",0),w=p.getInt("width",0),h=p.getInt("height",0);
            String resource=p.getString("item");
            for(int y=y0;y<y0+h;y++) for(int x=x0;x<x0+w;x++) {
                if(resource.equals("sand")) world.tile(x,y).setFloor(Blocks.sand.asFloor());
                else if(resource.equals("water")) world.tile(x,y).setFloor(Blocks.water.asFloor());
                else world.tile(x,y).setOverlay(block("ore-"+resource));
            }
        }
        for(Jval p:task.get("obstacles").asArray()) world.tile(p.asArray().get(0).asInt(),p.asArray().get(1).asInt()).setBlock(Blocks.stoneWall);
        Jval cp=task.get("core");
        world.tile(cp.getInt("x",0),cp.getInt("y",0)).setBlock(Blocks.coreShard,Team.sharded,0);
        Building core=world.build(cp.getInt("x",0),cp.getInt("y",0));
        List<Jval> placements=new ArrayList<>();
        for(Jval p:blueprint.get("buildings").asArray()) placements.add(p);
        placements.sort(Comparator.comparingInt((Jval p)->p.getInt("y",0)).thenComparingInt(p->p.getInt("x",0)));
        List<Building> buildings=new ArrayList<>();
        int buildCost=0;
        for(Jval p:placements) {
            String name=p.getString("block");
            boolean permits=false;for(Jval n:task.get("allowed_blocks").asArray()) if(n.asString().equals(name))permits=true;
            if(!permits||!Arrays.asList(allowed).contains(name)) throw new IllegalArgumentException("Block not permitted: "+name);
            Block b=block(name);int x=p.getInt("x",-1),y=p.getInt("y",-1),r=p.getInt("rotation",0),off=-(b.size-1)/2;
            if(r<0||r>3)throw new IllegalArgumentException("Invalid rotation");
            for(int dy=0;dy<b.size;dy++) for(int dx=0;dx<b.size;dx++){
                Tile t=world.tile(x+off+dx,y+off+dy);
                if(t==null||t.block()!=Blocks.air) throw new IllegalArgumentException("Overlap, obstacle, or out-of-bounds at "+x+","+y);
            }
            if(!Build.validPlaceIgnoreUnits(b,Team.sharded,x,y,r,false,false)) throw new IllegalArgumentException("Illegal placement at "+x+","+y);
            buildCost+=cost(b);
            if(buildCost>task.getInt("budget",0))throw new IllegalArgumentException("Construction budget exceeded");
            world.tile(x,y).setBlock(b,Team.sharded,r);buildings.add(world.build(x,y));
        }
        world.endMapLoad();
        // Explicit links use the engine's own configuration validation, range and node limits.
        for(int i=0;i<placements.size();i++){
            Jval p=placements.get(i);Building b=buildings.get(i);
            if(p.has("item")) {
                Item item=content.getByName(ContentType.item,p.getString("item"));
                if(item==null||!(b.block.name.equals("sorter")||b.block.name.equals("inverted-sorter")))throw new IllegalArgumentException("Unsupported item configuration");
                b.configured(null,item);
            }
            if(p.has("links")) {
                if(!(b.block instanceof PowerNode))throw new IllegalArgumentException("Only power nodes support links");
                Point2[] links=new Point2[p.get("links").asArray().size]; int k=0;
                for(Jval v:p.get("links").asArray())links[k++]=new Point2(v.asArray().get(0).asInt()-b.tileX(),v.asArray().get(1).asInt()-b.tileY());
                b.configured(null,links);
                for(Point2 v:links)if(!b.power.links.contains(Point2.pack(b.tileX()+v.x,b.tileY()+v.y)))throw new IllegalArgumentException("Invalid power link");
            }
        }
        core.items.clear();
        canonicalizeNeighbors(buildings,core);
        state.set(State.playing);
        Time.setInternalTime(0);Time.time=0;Time.globalTime=0;Time.delta=1;
        Jval frames=Jval.newArray(),deliveries=Jval.newArray();
        frames.add(snapshot(0,buildings,core));
        Item goal=content.getByName(ContentType.item,task.getString("goal"));
        int previous=0,first=-1;
        for(int tick=1;tick<=ticks;tick++){
            Time.globalTime=tick;
            logic.update();
            int count=core.items.get(goal);
            if(count!=previous){
                if(first<0)first=tick;
                deliveries.add(Jval.newObject().put("tick",tick).put("count",count).put("delta",count-previous));
                previous=count;
            }
            if(tick%120==0||tick==ticks)frames.add(snapshot(tick,buildings,core));
        }
        return Jval.newObject().put("valid",true).put("score",core.items.get(goal)).put("first_delivery_tick",first)
            .put("build_cost",buildCost).put("core_items",inventory(core)).put("ticks",ticks).put("frames",frames).put("deliveries",deliveries);
    }
    public static void main(String[] args)throws Exception {
        Jval input=Jval.read(Files.readString(Path.of(args[0])));output=args[1];
        new HeadlessApplication(new ApplicationListener(){public void init(){
            try{
                initEngine(Path.of(args[2]));
                Jval result;
                if(input.getString("mode","").equals("catalog"))result=catalog();
                else try{result=simulate(input);}catch(IllegalArgumentException e){
                    result=Jval.newObject().put("valid",false).put("score",0).put("error",e.getMessage());
                }
                Files.writeString(Path.of(output),result.toString(Jval.Jformat.plain));
                System.exit(0);
            }catch(Throwable e){e.printStackTrace();System.exit(2);}
        }},e->{e.printStackTrace();System.exit(2);});
    }
}
