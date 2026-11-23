'use strict';
// Shared visible-state implementation for three fixed, hand-authored probe styles.
// These are coverage opponents, not a claim of independent strong algorithms.
const {dex,damage,multiplier}=require('./common.cjs');
const id=x=>String(x||'').toLowerCase().replace(/[^a-z0-9]/g,'');
const HAZARDS=new Set(['stealthrock','spikes','toxicspikes','stickyweb']);
const CLEAR=new Set(['rapidspin','defog','mortalspin','tidyup']);
const DENY=new Set(['haze','clearsmog','whirlwind','roar','dragontail']);
function boosts(o){
 const state={p1:{},p2:{}};
 for(const line of o.history){const p=line.split('|'),s=p[2]?.slice(0,2);
  if(p[1]==='-clearallboost'){state.p1={};state.p2={};continue;}
  if(!state[s])continue;
  if(['switch','drag','replace','-clearboost'].includes(p[1]))state[s]={};
  if(['-boost','-unboost'].includes(p[1]))state[s][p[3]]=(state[s][p[3]]||0)+Number(p[4])*(p[1]==='-boost'?1:-1);
  if(p[1]==='-setboost')state[s][p[3]]=Number(p[4]);
  if(p[1]==='-clearpositiveboost')for(const k in state[s])state[s][k]=Math.min(0,state[s][k]);
  if(p[1]==='-clearnegativeboost')for(const k in state[s])state[s][k]=Math.max(0,state[s][k]);
 }
 return {own:state[o.side],enemy:state[o.side==='p1'?'p2':'p1']};
}
exports.create=style=>{
 let lastSwitch=-99,lastSetup=-99,lastHazard=-99;let setups=0,hazards=0;
 return o=>{
  const a=o.active,foe=o.opponent,stage=boosts(o);
  const ownHaz=Object.keys(o.own_side_conditions).filter(x=>HAZARDS.has(id(x.replace('move: ',''))));
  const theirs=Object.keys(o.opponent_side_conditions).map(x=>id(x.replace('move: ','')));
  const danger=Math.max(0,...Object.values(stage.enemy));
  const active={...a,boosts:stage.own};
  function denialWorks(m){return DENY.has(m.id)&&!(m.id==='clearsmog'&&foe?.types.includes('Steel'))&&
   !(m.id==='dragontail'&&foe?.types.includes('Fairy'));}
  function offense(m,p){
   let v=damage(m,p,foe);
   const weather=id(o.weather),ability=id(foe?.ability);
   if(['raindance','primordialsea'].includes(weather)){if(m.type==='Water')v*=1.5;if(m.type==='Fire')v*=.5;}
   if(['sunnyday','desolateland'].includes(weather)){if(m.type==='Fire')v*=1.5;if(m.type==='Water')v*=.5;}
   if((m.type==='Ground'&&ability==='levitate')||(m.type==='Water'&&['waterabsorb','stormdrain','dryskin'].includes(ability))||
      (m.type==='Electric'&&['voltabsorb','motordrive','lightningrod'].includes(ability))||(m.type==='Fire'&&ability==='flashfire'))v=0;
   if(p?.status==='brn'&&m.category==='Physical'&&id(p.ability)!=='guts')v*=.5;
   if(m.priority>0&&foe?.hp_fraction<.25)v*=1.4;
   return 100*v/(v+100); // Keep support choices on a comparable scale to attack estimates.
  }
  function score(action){
   if(action.kind==='lead'){
    const p=o.own_team[action.slot-1],moves=p.moves.map(x=>dex.moves.get(x));
    const role=style==='hazard-control'?moves.some(m=>HAZARDS.has(m.id)):
     style==='setup-pressure'?moves.some(m=>m.boosts&&m.target==='self'):
     moves.some(m=>DENY.has(m.id));
    return (role?200:0)+p.base_stats.spe*.15+Math.max(p.base_stats.atk,p.base_stats.spa)*.05;
   }
   if(action.kind==='switch'){
    const p=o.own_team[action.slot-1],best=Math.max(0,...p.moves.map(m=>offense(dex.moves.get(m),p)));
    const weakness=Math.max(1,...(foe?.types||[]).map(t=>multiplier(t,p)));
    if(style==='anti-setup'&&danger>=2&&p.hp_fraction>.4&&p.moves.some(x=>denialWorks(dex.moves.get(x))))
     return 105-weakness*5-(o.turn-lastSwitch<3?45:0);
    return best*.65-weakness*8+p.hp_fraction*10-(o.turn-lastSwitch<3?60:10)-ownHaz.length*8;
   }
   const m=action.move,p=action.terastallize?{...active,types:[action.terastallize]}:active;
   let v=offense(m,p);
   if(m.heal&&a.hp_fraction<.45)v=Math.max(v,95*(1-a.hp_fraction));
   if(m.id==='rest'&&a.hp_fraction<.3&&!a.status)v=76;
   if(m.id==='sleeptalk'&&a.status==='slp')v=120;
   if(HAZARDS.has(m.id)&&!theirs.includes(m.id)&&hazards<3&&o.turn-lastHazard>=4&&a.hp_fraction>.25&&o.turn<50)
    v=style==='hazard-control'?105:45;
   if(CLEAR.has(m.id)&&ownHaz.length&&!(m.id==='rapidspin'&&foe?.types.includes('Ghost')))
    v=style==='hazard-control'?120:95;
   if(m.boosts&&m.target==='self'&&a.hp_fraction>.62&&setups<3&&o.turn-lastSetup>=3&&
      Object.entries(m.boosts).some(([k,n])=>n>0&&(stage.own[k]||0)<2)&&id(foe?.ability)!=='unaware')
    v=style==='setup-pressure'?110:30;
   if(denialWorks(m)&&danger>=2)
    v=style==='anti-setup'?140:125;
   if(m.status&&!foe?.status&&foe?.hp_fraction>.4)v=Math.max(v,style==='anti-setup'?55:40);
   if(action.terastallize)v-=7;
   return v;
  }
  const best=o.legal_actions.reduce((x,y)=>score(y)>score(x)?y:x);
  if(best.kind==='switch')lastSwitch=o.turn;
  if(best.kind==='move'){
   if(HAZARDS.has(best.move.id)){hazards++;lastHazard=o.turn;}
   if(best.move.boosts&&best.move.target==='self'){setups++;lastSetup=o.turn;}
  }
  return best.id;
 };
};
exports.visibleBoosts=boosts;
