'use strict';
const g=require('./vendor/engine.cjs');
const CLASSES=[g.MetaBeltBuilding,g.MetaCutterBuilding,g.MetaRotaterBuilding,g.MetaStackerBuilding,
 g.MetaPainterBuilding,g.MetaMixerBuilding,g.MetaBalancerBuilding,g.MetaTrashBuilding,
 g.MetaUndergroundBeltBuilding,g.MetaConstantProducerBuilding,g.MetaGoalAcceptorBuilding];
for(const C of CLASSES)g.gMetaBuildingRegistry.register(C);
for(const C of CLASSES)for(const v of C.getAllVariantCombinations())
 g.registerBuildingVariant(v.internalId,C,v.variant,v.rotationVariant||0);
g.buildBuildingCodeCache();
const COSTS={belt:1,cutter:8,rotater:4,stacker:12,painter:10,mixer:8,balancer:4,trash:1,underground_belt:4};
const SYSTEMS=[['itemAcceptor',g.ItemAcceptorSystem],['belt',g.BeltSystem],
 ['undergroundBelt',g.UndergroundBeltSystem],['itemProcessor',g.ItemProcessorSystem],
 ['itemEjector',g.ItemEjectorSystem],['constantProducer',g.ConstantProducerSystem]];
function key(item){return item?.definition?item.definition.getHash():item?.color||null;}
function entity(root,b){
 const meta=g.gMetaBuildingRegistry.findById(b.type);
 const variant=b.variant||'default',rv=b.rotationVariant||0;
 if(!meta.constructor.getAllVariantCombinations().some(v=>v.variant===variant&&(v.rotationVariant||0)===rv))throw Error('unsupported building variant');
 return meta.createEntity({root,origin:new g.Vector(b.x,b.y),rotation:b.rotation||0,
  originalRotation:b.rotation||0,variant,rotationVariant:rv});
}
function catalog(){
 return Object.keys(COSTS).flatMap(type=>{
  const meta=g.gMetaBuildingRegistry.findById(type);
  return meta.constructor.getAllVariantCombinations().map(v=>{
   const b={type,variant:v.variant,rotationVariant:v.rotationVariant||0,x:0,y:0,rotation:0};
   const e=entity({},b),c=e.components;
   return {...b,cost:COSTS[type],size:meta.getDimensions(v.variant),
    inputs:c.ItemAcceptor?.slots.map(s=>({pos:s.pos,direction:s.direction,filter:s.filter}))||[],
    outputs:c.ItemEjector?.slots.map(s=>({pos:s.pos,direction:s.direction}))||[],
    processor:c.ItemProcessor?.type||null};
  });
 });
}
function create(task,blueprint){
 if(!blueprint||Object.keys(blueprint).some(k=>!['version','buildings'].includes(k))||blueprint.version!==1||!Array.isArray(blueprint.buildings))throw Error('expected {version:1,buildings:[...]}');
 if(blueprint.buildings.length>task.max_buildings)throw Error('too many buildings');
 const root=new g.GameRoot({settings:{getAllSettings:()=>({simplifiedBelts:true})}});
 root.dynamicTickrate={deltaSeconds:1/task.tick_rate};
 let tick=0;root.time={now:()=>tick/task.tick_rate,realtimeNow:()=>tick/task.tick_rate};
 root.gameMode={throughputDoesNotMatter:()=>false,getIsEditor:()=>false};
 root.hubGoals=Object.create(g.HubGoals.prototype);root.hubGoals.root=root;
 root.hubGoals.upgradeImprovements={belt:1,miner:1,processors:1,painting:1};
 root.shapeDefinitionMgr=new g.ShapeDefinitionManager(root);
 root.entityMgr=new g.EntityManager(root);
 const map=new Map();
 root.map={getLayerContentXY:(x,y,layer)=>layer==='regular'?map.get(`${x},${y}`)||null:null,
  getTileContent:(tile,layer)=>layer==='regular'?map.get(`${tile.x},${tile.y}`)||null:null,
  getLayersContentsMultipleXY:(x,y)=>{const e=map.get(`${x},${y}`);return e?[e]:[];}};
 root.systemMgr={systems:{}};
 for(const [id,C]of SYSTEMS)root.systemMgr.systems[id]=new C(root);
 let cost=0;const layout=[],goals=[],deliveries=[];
 const blocked=new Set(task.blocked.map(([x,y])=>`${x},${y}`));
 function place(b,fixed=false){
  if(!fixed){
   if(Object.keys(b).some(k=>!['type','x','y','rotation','variant','rotationVariant'].includes(k)))throw Error('unknown building field');
   if(!task.allowed.includes(b.type)||!Object.hasOwn(COSTS,b.type))throw Error('building is not allowed');
   cost+=COSTS[b.type];if(cost>task.build_budget)throw Error('build budget exceeded');
  }
  if(!Number.isSafeInteger(b.x)||!Number.isSafeInteger(b.y)||b.x<0||b.y<0||b.x>=task.width||b.y>=task.height||![0,90,180,270].includes(b.rotation??0)||!Number.isInteger(b.rotationVariant??0))throw Error('invalid position or rotation');
  const e=entity(root,b),s=e.components.StaticMapEntity,bounds=s.getTileSpaceBounds();
  for(let x=bounds.x;x<bounds.right();x++)for(let y=bounds.y;y<bounds.bottom();y++){
   if(x<0||y<0||x>=task.width||y>=task.height)throw Error('building outside map');
   if(map.has(`${x},${y}`)||blocked.has(`${x},${y}`))throw Error('building overlap or blocked tile');
   map.set(`${x},${y}`,e);
  }
  if(b.type==='constant_producer')e.components.ConstantSignal.signal=b.color?g.COLOR_ITEM_SINGLETONS[b.color]:root.shapeDefinitionMgr.getShapeItemFromShortKey(b.shape);
  if(b.type==='goal_acceptor'){
   e.components.GoalAcceptor.item=root.shapeDefinitionMgr.getShapeItemFromShortKey(b.shape);goals.push(e);
  }
  root.entityMgr.registerEntity(e);
  layout.push({...b,fixed,uid:e.uid,bounds:{x:bounds.x,y:bounds.y,w:bounds.w,h:bounds.h}});
  return e;
 }
 // Stable spatial order makes array order irrelevant to arbitration and scoring.
 const order=(a,b)=>a.y-b.y||a.x-b.x||a.type.localeCompare(b.type);
 for(const b of [...task.sources,...task.goals].sort(order))place(b,true);
 for(const b of [...blueprint.buildings].sort(order))place(b);
 root.systemMgr.systems.belt.recomputeAllBeltPaths();
 root.systemMgr.systems.itemEjector.recomputeCacheFull();
 root.signals.postLoadHook.dispatch();root.gameInitialized=true;
 const processor=root.systemMgr.systems.itemProcessor;
 const goalHandler=processor.handlers.goal;
 processor.handlers.goal=payload=>{
  const item=payload.items.get(0),wanted=payload.entity.components.GoalAcceptor.item;
  deliveries.push({tick,goal:payload.entity.uid,shape:key(item),correct:item.equals(wanted)});
  goalHandler(payload); // Read-only scoring hook; preserve original processing.
 };
 function snapshot(){
  const items=[];
  for(const p of root.systemMgr.systems.belt.beltPaths){
   let d=p.spacingToFirstItem,index=0,offset=0;
   for(const [gap,item]of p.items){
    while(index<p.entityPath.length-1&&d-offset>p.entityPath[index].components.Belt.getEffectiveLengthTiles()){
     offset+=p.entityPath[index].components.Belt.getEffectiveLengthTiles();index++;
    }
    const e=p.entityPath[index],s=e.components.StaticMapEntity;
    const v=e.components.Belt.transformBeltToLocalSpace(Math.max(0,Math.min(d-offset,e.components.Belt.getEffectiveLengthTiles())));
    const rotated=v.rotateFastMultipleOf90(s.rotation);
    items.push({x:s.origin.x+.5+rotated.x,y:s.origin.y+.5+rotated.y,item:key(item)});d+=gap;
   }
  }
  const machines=root.entityMgr.entities.filter(e=>e.components.ItemProcessor).map(e=>({uid:e.uid,
   waiting:e.components.ItemProcessor.inputSlots?.size||0,processing:e.components.ItemProcessor.ongoingCharges.length,
   queued:e.components.ItemProcessor.queuedEjects.length}));
  return {tick,delivered:deliveries.filter(x=>x.correct).length,items,machines};
 }
 return {root,layout,cost,deliveries,snapshot,get tick(){return tick;},step(){
  tick++;for(const [id]of SYSTEMS)root.systemMgr.systems[id].update();
 }};
}
function simulate(task,blueprint,{replay=true}={}){
 const sim=create(task,blueprint),frames=replay?[sim.snapshot()]:[];
 for(let n=0;n<task.duration_seconds*task.tick_rate;n++){
  sim.step();if(replay&&sim.tick%task.replay_every_ticks===0)frames.push(sim.snapshot());
 }
 const correct=sim.deliveries.filter(x=>x.correct);
 return {task_id:task.id,valid:true,score:correct.length,delivered:correct.length,
  wrong_deliveries:sim.deliveries.length-correct.length,first_delivery_tick:correct[0]?.tick??null,
  build_cost:sim.cost,building_count:blueprint.buildings.length,ticks:sim.tick,
  layout:sim.layout,deliveries:sim.deliveries,frames};
}
module.exports={create,simulate,catalog,COSTS,g};
