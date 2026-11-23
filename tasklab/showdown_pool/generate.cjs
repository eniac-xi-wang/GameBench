'use strict';
// Candidate distribution construction. Legality belongs to the pinned native engine.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {Dex,TeamValidator}=require('../../pokemon-showdown/dist/sim');
const {profiles}=require('../showdown_candidates.cjs');
const clone=structuredClone,id=x=>String(x).toLowerCase().replace(/[^a-z0-9]/g,'');
const hash=x=>crypto.createHash('sha256').update(typeof x==='string'?x:JSON.stringify(x)).digest('hex');
const FORMATS=['gen9ou','gen9monotype','gen9ubers'];
const SETUP=new Set(['swordsdance','dragondance','calmmind','nastyplot','growth','irondefense','bellydrum','bulkup']);
const HAZARD=new Set(['stealthrock','spikes','toxicspikes','stickyweb']);
const CLEAR=new Set(['rapidspin','defog','mortalspin','tidyup']);
const DENY=new Set(['haze','clearsmog','whirlwind','roar','dragontail']);
const PIVOT=new Set(['uturn','voltswitch','flipturn','chillyreception','teleport','partingshot']);
const weatherAbilities=new Set(['drizzle','drought','sandstream','snowwarning','orichalcumpulse']);
function rng(seed){let counter=0;return n=>parseInt(hash(seed+'/'+counter++).slice(0,12),16)%n;}
function shuffle(a,r){a=clone(a);for(let i=a.length-1;i>0;i--){const j=r(i+1);[a[i],a[j]]=[a[j],a[i]];}return a;}
function normalize(m){return {species:Dex.species.get(m.species).name,ability:m.ability,item:m.item,nature:m.nature,
 moves:m.moves.map(x=>Dex.moves.get(x).name),evs:Object.fromEntries(['hp','atk','def','spa','spd','spe'].map(k=>[k,m.evs?.[k]||0])),
 ivs:Object.fromEntries(['hp','atk','def','spa','spd','spe'].map(k=>[k,m.ivs?.[k]??31])),level:100,teraType:m.teraType||Dex.species.get(m.species).types[0]};}
function setKey(m){const n=normalize(m);n.moves.sort();return hash(n);}
function speciesKey(t){return t.map(m=>id(Dex.species.get(m.species).baseSpecies)).sort().join('|');}
function roles(m){const moves=m.moves.map(id);return {hazard:moves.some(x=>HAZARD.has(x)),clear:moves.some(x=>CLEAR.has(x)),
 setup:moves.some(x=>SETUP.has(x)),deny:moves.some(x=>DENY.has(x)),unaware:id(m.ability)==='unaware',pivot:moves.some(x=>PIVOT.has(x))};}
function fresh(species,ability,item,nature,moves,kind='physical'){
 return normalize({species,ability,item,nature,moves:moves.split(','),evs:kind==='special'?{spa:252,spe:252,spd:4}:kind==='defense'?{hp:252,def:252,spd:4}:{atk:252,spe:252,spd:4}});
}
const extra=[
 fresh('Azumarill','Huge Power','Assault Vest','Adamant','Liquidation,Play Rough,Aqua Jet,Knock Off'),
 fresh('Samurott-Hisui','Sharpness','Choice Scarf','Jolly','Ceaseless Edge,Razor Shell,Knock Off,Sacred Sword'),
 fresh('Empoleon','Competitive','Leftovers','Calm','Surf,Flash Cannon,Roost,Stealth Rock','defense'),
 fresh('Quaquaval','Moxie','Heavy-Duty Boots','Jolly','Aqua Step,Close Combat,Rapid Spin,Roost'),
 fresh('Heatran','Flash Fire','Leftovers','Calm','Magma Storm,Earth Power,Stealth Rock,Taunt','defense'),
 fresh('Lucario','Inner Focus','Life Orb','Jolly','Close Combat,Meteor Mash,Extreme Speed,Swords Dance'),
 fresh('Metagross','Clear Body','Assault Vest','Adamant','Meteor Mash,Bullet Punch,Earthquake,Ice Punch'),
 fresh('Gliscor','Poison Heal','Toxic Orb','Impish','Earthquake,Knock Off,Spikes,Protect','defense'),
 fresh('Zapdos','Static','Heavy-Duty Boots','Timid','Thunderbolt,Hurricane,Volt Switch,Roost','special'),
 fresh('Tornadus-Therian','Regenerator','Heavy-Duty Boots','Timid','Hurricane,Knock Off,U-turn,Taunt','special'),
 fresh('Mandibuzz','Overcoat','Heavy-Duty Boots','Impish','Foul Play,Roost,Defog,U-turn','defense'),
 fresh('Kommo-o','Bulletproof','Leftovers','Impish','Body Press,Dragon Tail,Iron Defense,Stealth Rock','defense'),
 fresh('Latias','Levitate','Leftovers','Timid','Dragon Pulse,Psyshock,Calm Mind,Recover','special'),
 fresh('Latios','Levitate','Choice Specs','Timid','Draco Meteor,Psyshock,Surf,Trick','special'),
 fresh('Noivern','Infiltrator','Heavy-Duty Boots','Timid','Draco Meteor,Hurricane,U-turn,Roost','special'),
 fresh('Corviknight','Pressure','Leftovers','Impish','Body Press,Roost,Defog,U-turn','defense'),
 fresh('Skarmory','Sturdy','Rocky Helmet','Impish','Spikes,Roost,Body Press,Whirlwind','defense'),
 fresh('Garchomp','Rough Skin','Rocky Helmet','Impish','Earthquake,Dragon Tail,Stealth Rock,Fire Blast','defense'),
 fresh('Toxapex','Regenerator','Leftovers','Bold','Surf,Recover,Haze,Toxic Spikes','defense'),
 fresh('Dragonite','Multiscale','Heavy-Duty Boots','Adamant','Dragon Dance,Dragon Claw,Earthquake,Roost'),
 fresh('Scizor','Technician','Leftovers','Adamant','Swords Dance,Bullet Punch,Close Combat,U-turn'),
 fresh('Clefable','Unaware','Leftovers','Bold','Moonblast,Moonlight,Knock Off,Thunder Wave','defense'),
];
// Move alternatives are curated, then natively validated; no random EV/tera padding.
const alternateMoves={
 'Dragonite':'Fire Punch','Rotom-Wash':'Thunderbolt','Greninja':'Surf','Gengar':'Energy Ball',
 'Sylveon':'Psyshock','Meowscarada':'Triple Axel','Arcanine':'Close Combat','Pelipper':'Weather Ball',
 'Barraskewda':'Aqua Jet','Tyranitar':'Ice Punch','Salamence':'Fire Fang','Hydreigon':'Flash Cannon',
 'Mamoswine':'Icicle Crash','Goodra-Hisui':'Dragon Pulse','Dragapult':'Thunderbolt','Iron Valiant':'Psyshock',
 'Venusaur':'Earth Power','Cetitan':'Ice Shard','Talonflame':'U-turn','Quaquaval':'Ice Spinner',
 'Azumarill':'Superpower','Mewtwo':'Aura Sphere','Eternatus':'Recover','Rayquaza':'Waterfall',
 'Dialga-Origin':'Dragon Pulse','Kyogre':'Surf','Koraidon':'Outrage','Groudon':'Fire Punch',
};
function semantic(m){const status=m.moves.map(x=>Dex.moves.get(x)).filter(x=>x.category==='Status');
 if(id(m.item)==='assaultvest'&&status.length)return false;
 if(id(m.item).startsWith('choice')&&status.some(x=>!['trick','switcheroo'].includes(x.id)))return false;
 return true;}
function bank(){
 const bases=[...profiles.flatMap(p=>p.teams.flatMap(t=>t.team)),...extra].map(normalize);
 const candidates=new Map();
 for(const m of bases){
  const variants=[m];const alt=alternateMoves[m.species];
  if(alt&&!m.moves.map(id).includes(id(alt))){const n=clone(m);const index=n.moves.findLastIndex(x=>Dex.moves.get(x).category!=='Status');if(index>=0){n.moves[index]=alt;variants.push(n);}}
  for(const v of variants){
   const required=Dex.species.get(v.species).requiredItem;
   const choices=required||id(v.ability)==='poisonheal'?[v.item]:[v.item,'Leftovers','Heavy-Duty Boots'];
   for(const item of choices){const n={...clone(v),item};if(semantic(n))candidates.set(setKey(n),n);}
  }
 }
 const catalog={},rejections={};
 for(const format of FORMATS){
  catalog[format]={};rejections[format]=[];
  const validator=new TeamValidator(format);
  for(const [key,m] of candidates){
   const errors=validator.validateTeam([clone(m)]);
   if(errors){rejections[format].push({set_id:key,species:m.species,errors});continue;}
   (catalog[format][m.species]??=[]).push({id:key,set:m,roles:roles(m)});
  }
 }
 return {catalog,rejections};
}
const weatherCores=[
 {name:'rain',core:[['Pelipper','Drizzle'],['Barraskewda','Swift Swim']]},
 {name:'sun',core:[['Torkoal','Drought'],['Venusaur','Chlorophyll']]},
 {name:'sand',core:[['Tyranitar','Sand Stream'],['Excadrill','Sand Rush']]},
 {name:'snow',core:[['Ninetales-Alola','Snow Warning'],['Cetitan','Slush Rush']]},
];
const uberNames=new Set(profiles.find(p=>p.id==='gen9-ubers').teams.flatMap(t=>t.team.map(m=>m.species)));
function drawTeam(profile,catalog,seed,subgroup){
 const r=rng(seed),entries=catalog[profile.formatid],chosen=[];
 let names=Object.keys(entries).sort();
 function pick(predicate,allowed=names){
  const groups=allowed.filter(n=>!chosen.some(c=>c.set.species===n)).map(n=>entries[n].filter(predicate)).filter(x=>x.length);
  if(!groups.length)throw Error('No compatible core: '+profile.id);
  const opts=groups[r(groups.length)];chosen.push(clone(opts[r(opts.length)]));
 }
 let tag='balanced';
 if(profile.id==='gen9-monotype'){
  tag=['Water','Steel','Flying','Dragon'][subgroup%4];names=names.filter(n=>Dex.species.get(n).types.includes(tag));
 }else if(profile.id==='gen9-ubers'){
  names=names.filter(n=>uberNames.has(n));tag='ubers';
 }else if(profile.id==='ou-weather-cores'){
  const core=weatherCores[subgroup%4];tag=core.name;
  for(const [species,ability] of core.core)pick(x=>x.set.ability===ability,[species]);
  names=names.filter(n=>!entries[n].some(x=>weatherAbilities.has(id(x.set.ability))));
 }else if(profile.id==='ou-hazards-pivot'){
  tag='hazard-clear-pivot';pick(x=>x.roles.hazard);pick(x=>x.roles.clear);pick(x=>x.roles.pivot);
 }else if(profile.id==='ou-setup-denial'){
  tag='setup-denial';pick(x=>x.roles.setup);pick(x=>x.roles.deny);pick(x=>x.roles.pivot||x.roles.unaware);
 }else{
  pick(x=>x.roles.pivot);pick(x=>x.roles.setup||x.roles.hazard);
 }
 while(chosen.length<6)pick(()=>true);
 const team=shuffle(chosen.map(x=>clone(x.set)),r);
 return {tag,team,set_ids:team.map(setKey),species_key:speciesKey(team)};
}
function sample(catalog,counts,seed,excluded=[]){
 if(!Object.keys(counts).length||Object.values(counts).some(n=>!Number.isSafeInteger(n)||n<1||n>10000))throw Error('Invalid positive team count');
 const seen=new Set(excluded),splits={},stats={};
 for(const [split,count] of Object.entries(counts)){
  splits[split]={};stats[split]={};
  for(const profile of profiles){
   const teams=[],failures=[];let duplicate=0;
   for(let attempt=0;teams.length<count&&attempt<20000;attempt++){
    const t=drawTeam(profile,catalog,`${seed}/${split}/${profile.id}/${attempt}`,teams.length);
    const key=profile.formatid+'/'+t.species_key;
    if(seen.has(key)){duplicate++;continue;}
    const errors=new TeamValidator(profile.formatid).validateTeam(clone(t.team));
    if(errors){failures.push({attempt,errors});continue;}
    seen.add(key);teams.push({...t,id:'team-'+hash([profile.id,split,t.species_key,t.set_ids]).slice(0,16)});
   }
   if(teams.length!==count)throw Error(`Sampling exhausted ${split}/${profile.id}: ${teams.length}/${count}`);
   splits[split][profile.id]=teams;stats[split][profile.id]={accepted:teams.length,duplicate_rejections:duplicate,legality_rejections:failures};
  }
 }
 return {splits,stats};
}
function generate(out){
 if(fs.existsSync(out))throw Error('Use a new directory');
 const b=bank();const counts={train:32,validation:16,'test-smoke':16};
 const data=sample(b.catalog,counts,'showdown-distribution-v1');
 fs.mkdirSync(out,{recursive:true});
 const save=(file,obj)=>fs.writeFileSync(path.join(out,file),JSON.stringify(obj,null,2)+'\n');
 save('set-bank.json',b.catalog);save('legality-rejections.json',b.rejections);save('generation.json',data.stats);
 for(const [split,items] of Object.entries(data.splits))save(split+'.json',items);
 const distribution={version:1,scope:'public candidate distribution audit; no agent run',model_api_calls:0,
  profiles:profiles.map(p=>({id:p.id,name:p.name,formatid:p.formatid})),split_counts_per_profile:counts,
  sampling_seed:'showdown-distribution-v1',seed_rule:'separate team generation and battle seeds; no policy control',
  sampling:'role-constrained team composition; independent random set choice per team; shuffled order',
  exclusion:'order-independent base-species combination, globally across strata sharing a format and across all splits',
  shared_information:'public species and set bank; no claim of unseen species/loadout generalization',
  final_test:'not generated; test-smoke is public consumed acceptance data and must be excluded from future final sampling',
  catalog:Object.fromEntries(FORMATS.map(f=>[f,{species:Object.keys(b.catalog[f]).length,sets:Object.values(b.catalog[f]).flat().length,
   move_signatures:Object.fromEntries(Object.entries(b.catalog[f]).map(([n,v])=>[n,new Set(v.map(x=>x.set.moves.map(id).sort().join(','))).size]))}]))};
 save('distribution.json',distribution);console.log(JSON.stringify(distribution));
}
if(require.main===module){
 const [command,out,input]=process.argv.slice(2);
 if(command==='generate')generate(path.resolve(out));
 else if(command==='sample'){
  const spec=JSON.parse(fs.readFileSync(input));const data=sample(spec.catalog,spec.counts,spec.seed,spec.excluded);
  fs.writeFileSync(out,JSON.stringify(data,null,2)+'\n');
 }else throw Error('Use generate OUT or sample OUT INPUT');
}
module.exports={bank,sample,drawTeam,setKey,speciesKey,roles,profiles,rng,normalize};
