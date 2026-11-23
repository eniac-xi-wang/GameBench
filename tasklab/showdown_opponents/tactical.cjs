'use strict';
// Transparent hand-authored probe opponent, not an LLM result or optimal player.
const {dex,damage,multiplier}=require('./common.cjs');
let lastSwitch=-100,lastSetup=-100;
const id=x=>String(x||'').toLowerCase().replace(/[^a-z0-9]/g,'');
exports.chooseAction=o=>{
 const active=o.active,foe=o.opponent;
 const actions=o.legal_actions;
 const canSetup=!['unaware'].includes(id(foe?.ability));
 const weather=id(o.weather);
 const hazardCount=Object.keys(o.opponent_side_conditions).length;
 const ownHazards=Object.keys(o.own_side_conditions).filter(x=>/spikes|rock|web/i.test(x)).length;
 const foeBoost=Math.max(0,...Object.values(foe?.boosts||{}));
 const allies=o.own_team.filter(p=>!p.fainted);
 function attack(m,p,target){
  let score=damage(m,p,target);
  if(weather==='raindance'){if(m.type==='Water')score*=1.5;if(m.type==='Fire')score*=.5;}
  if(weather==='sunnyday'||weather==='desolateland'){if(m.type==='Fire')score*=1.5;if(m.type==='Water')score*=.5;}
  const a=id(target?.ability);
  if((m.type==='Ground'&&a==='levitate')||(m.type==='Water'&&['waterabsorb','stormdrain','dryskin'].includes(a))||
     (m.type==='Electric'&&['voltabsorb','motordrive','lightningrod'].includes(a))||(m.type==='Fire'&&a==='flashfire'))score=0;
  if(p?.status==='brn'&&m.category==='Physical'&&id(p.ability)!=='guts')score*=.5;
  if(m.priority>0&&target?.hp_fraction<.3)score*=1.6;
  return score;
 }
 function score(a){
  if(a.kind==='lead'){
   const p=o.own_team[a.slot-1],ability=id(p.ability||p.baseAbility);
   return Math.max(p.base_stats.atk,p.base_stats.spa)+p.base_stats.spe*.4+
    (['drizzle','drought','sandstream','snowwarning','orichalcumpulse'].includes(ability)?80:0);
  }
  if(a.kind==='switch'){
   const p=o.own_team[a.slot-1];
   const offense=Math.max(0,...p.moves.map(m=>attack(dex.moves.get(m),p,foe)));
   const incoming=Math.max(1,...(foe?.types||[]).map(t=>multiplier(t,p)));
   return offense*.55-incoming*24+p.hp_fraction*15-(o.turn-lastSwitch<=3?100:25)-ownHazards*12;
  }
  const m=dex.moves.get(a.move.id),p=a.terastallize?{...active,types:[a.terastallize]}:active;
  let v=attack(m,p,foe);
  if(m.heal&&active.hp_fraction<.55)v=120*(1-active.hp_fraction);
  if(m.id==='rest'&&active.hp_fraction<.3&&!active.status)v=55;
  if(m.id==='sleeptalk'&&active.status==='slp')v=120;
  if(m.boosts&&m.target==='self'&&canSetup&&active.hp_fraction>.65&&o.turn-lastSetup>2&&
   Object.entries(m.boosts).some(([s,n])=>n>0&&(active.boosts[s]||0)<2))v=75;
  if(['haze','clearsmog','whirlwind','roar'].includes(m.id)&&foeBoost>=2)v=Math.max(v,125);
  if(m.status&&!foe?.status&&foe?.hp_fraction>.35){
   let legal=true;
   if(['psn','tox'].includes(m.status)&&foe.types.some(t=>['Poison','Steel'].includes(t)))legal=false;
   if(m.status==='brn'&&foe.types.includes('Fire'))legal=false;
   if(m.status==='par'&&foe.types.includes('Electric'))legal=false;
   if(legal)v=50;
  }
  if(m.sideCondition&&!o.opponent_side_conditions['move: '+m.name]&&['stealthrock','spikes','toxicspikes','stickyweb'].includes(m.id)&&o.turn<25)v=62-hazardCount*8;
  if(['rapidspin','defog','mortalspin'].includes(m.id)&&ownHazards)v=Math.max(v,100);
  if(['uturn','voltswitch','flipturn'].includes(m.id)&&allies.length>1&&o.turn-lastSwitch>2)v*=1.1;
  if(a.terastallize)v-=8; // Preserve the one-time resource unless the observable gain covers the charge.
  return v;
 }
 const best=actions.reduce((a,b)=>score(b)>score(a)?b:a);
 if(best.kind==='switch')lastSwitch=o.turn;
 if(best.kind==='move'&&best.move.boosts&&best.move.target==='self')lastSetup=o.turn;
 return best.id;
};
