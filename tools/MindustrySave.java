import arc.ApplicationListener;
import arc.Events;
import arc.backend.headless.HeadlessApplication;
import arc.files.Fi;
import arc.struct.StringMap;
import arc.util.Time;
import arc.util.serialization.Jval;
import java.nio.file.Files;
import java.nio.file.Path;
import mindustry.content.Blocks;
import mindustry.core.GameState.State;
import mindustry.game.EventType.StateChangeEvent;
import mindustry.gen.Building;
import mindustry.gen.Player;
import mindustry.io.SaveIO;
import mindustry.maps.Map;
import mindustry.ctype.ContentType;
import mindustry.type.Item;
import static mindustry.Vars.*;

/** Write the populated benchmark world before its first production tick. */
public class MindustrySave {
    static void export(Jval input, Fi file) {
        Jval task = input.get("task");
        Events.on(StateChangeEvent.class, e -> {
            if (e.to != State.playing) return;
            state.map = new Map(StringMap.of("name", "GameBench - " + task.getString("id")));
            // The desktop client uses viewpos on load. Place it on the factory.
            player = Player.create();
            player.set(world.unitWidth() / 2f, world.unitHeight() / 2f);
            try { SaveIO.write(file); } finally { player = null; }
        });
        // Placement and configuration use the unchanged judge. The file is
        // captured at the state transition, before this single update runs.
        task.put("ticks", 1);
        FactoryRunner.simulate(input);
    }

    static void check(Jval input, Fi file) {
        Jval task = input.get("task");
        if (!SaveIO.isSaveValid(file)) throw new IllegalStateException("Invalid Mindustry save");
        SaveIO.load(file);
        Jval corePos = task.get("core");
        Building core = world.build(corePos.getInt("x", -1), corePos.getInt("y", -1));
        if (world.width() != task.getInt("width", -1) || world.height() != task.getInt("height", -1)
                || core == null || core.block != Blocks.coreShard || core.items.total() != 0) {
            throw new IllegalStateException("Loaded world differs from the initial map");
        }
        for (Jval row : input.get("blueprint").get("buildings").asArray()) {
            Building b = world.build(row.getInt("x", -1), row.getInt("y", -1));
            if (b == null || !b.block.name.equals(row.getString("block"))
                    || b.rotation != row.getInt("rotation", 0)) {
                throw new IllegalStateException("Loaded blueprint differs at " + row);
            }
        }
        Item target = content.getByName(ContentType.item, task.getString("goal"));
        state.set(State.playing);
        for (int tick = 1; tick <= task.getInt("ticks", -1); tick++) {
            Time.globalTime = tick;
            logic.update();
        }
        System.out.println("Loaded factory: " + task.getString("goal") + " = " + core.items.get(target)
                + " at tick " + task.getInt("ticks", -1));
    }

    public static void main(String[] args) {
        new HeadlessApplication(new ApplicationListener() {
            public void init() {
                try {
                    FactoryRunner.initEngine(Path.of(args[3]));
                    Jval input = Jval.read(Files.readString(Path.of(args[1])));
                    Fi file = new Fi(args[2]);
                    if (args[0].equals("save")) export(input, file);
                    else check(input, file);
                    System.exit(0);
                } catch (Throwable e) {
                    e.printStackTrace();
                    System.exit(1);
                }
            }
        });
    }
}
