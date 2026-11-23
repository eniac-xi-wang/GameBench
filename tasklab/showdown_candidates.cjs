'use strict';
// Candidate distributions for the pinned local engine; no claim about today's ladder.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {Dex,TeamValidator,Battle,Teams}=require('../pokemon-showdown/dist/sim');
const {observation}=require('../showdownbench/observations.cjs');
const {extractChannelMessages}=require('../pokemon-showdown/dist/sim/battle');
const old=JSON.parse(fs.readFileSync(path.join(__dirname,'../showdownbench/data/teams.json')));
const catalog=Object.fromEntries(old.flatMap(t=>t.team).map(m=>[m.species,structuredClone(m)]));
function mon(species,ability,item,nature,moves,kind='physical',teraType){
 return {name:species,species,ability,item,nature,moves:moves.split(','),level:100,
  evs:kind==='special'?{spa:252,spe:252,spd:4}:kind==='defense'?{hp:252,def:252,spd:4}:{atk:252,spe:252,spd:4},teraType:teraType||Dex.species.get(species).types[0]};
}
function add(...args){const m=mon(...args);catalog[m.species]=m;}
add('Torkoal','Drought','Heat Rock','Bold','Lava Plume,Stealth Rock,Rapid Spin,Body Press','defense');
add('Venusaur','Chlorophyll','Life Orb','Modest','Growth,Giga Drain,Sludge Bomb,Weather Ball','special');
add('Ninetales-Alola','Snow Warning','Light Clay','Timid','Aurora Veil,Blizzard,Moonblast,Encore','special');
add('Cetitan','Slush Rush','Heavy-Duty Boots','Adamant','Ice Spinner,Earthquake,Superpower,Belly Drum');
add('Kingambit','Supreme Overlord','Leftovers','Adamant','Kowtow Cleave,Sucker Punch,Iron Head,Swords Dance');
add('Gholdengo','Good as Gold','Leftovers','Timid','Make It Rain,Shadow Ball,Nasty Plot,Recover','special');
add('Dragapult','Infiltrator','Choice Specs','Timid','Draco Meteor,Shadow Ball,Flamethrower,U-turn','special');
add('Goodra-Hisui','Sap Sipper','Assault Vest','Modest','Draco Meteor,Flash Cannon,Flamethrower,Thunderbolt','special');
add('Talonflame','Flame Body','Heavy-Duty Boots','Jolly','Brave Bird,Flare Blitz,Will-O-Wisp,Roost');
add('Dondozo','Unaware','Leftovers','Impish','Liquidation,Body Press,Rest,Sleep Talk','defense');
add('Skeledirge','Unaware','Heavy-Duty Boots','Bold','Torch Song,Shadow Ball,Slack Off,Will-O-Wisp','defense');
add('Toxapex','Regenerator','Black Sludge','Bold','Surf,Recover,Haze,Toxic Spikes','defense');
add('Hippowdon','Sand Stream','Leftovers','Impish','Earthquake,Stealth Rock,Whirlwind,Slack Off','defense');
add('Volcarona','Flame Body','Heavy-Duty Boots','Timid','Quiver Dance,Fiery Dance,Bug Buzz,Giga Drain','special');
add('Hatterene','Magic Bounce','Leftovers','Bold','Calm Mind,Draining Kiss,Psyshock,Mystical Fire','defense');
add('Iron Valiant','Quark Drive','Booster Energy','Timid','Moonblast,Aura Sphere,Thunderbolt,Calm Mind','special');
add('Iron Treads','Quark Drive','Booster Energy','Jolly','Earthquake,Iron Head,Rapid Spin,Volt Switch');
add('Koraidon','Orichalcum Pulse','Choice Scarf','Jolly','Collision Course,Dragon Claw,Flare Blitz,U-turn');
add('Miraidon','Hadron Engine','Choice Specs','Timid','Electro Drift,Draco Meteor,Volt Switch,Overheat','special');
add('Dialga-Origin','Pressure','Adamant Crystal','Modest','Draco Meteor,Flash Cannon,Fire Blast,Thunder','special');
add('Zacian-Crowned','Intrepid Sword','Rusted Sword','Jolly','Behemoth Blade,Play Rough,Close Combat,Swords Dance');
add('Necrozma-Dusk-Mane','Prism Armor','Leftovers','Adamant','Sunsteel Strike,Earthquake,Dragon Dance,Morning Sun');
add('Kyogre','Drizzle','Choice Scarf','Timid','Water Spout,Origin Pulse,Thunder,Ice Beam','special');
add('Groudon','Drought','Leftovers','Adamant','Precipice Blades,Stone Edge,Stealth Rock,Swords Dance');
add('Ho-Oh','Regenerator','Heavy-Duty Boots','Impish','Sacred Fire,Brave Bird,Recover,Whirlwind','defense');
add('Arceus','Multitype','Heavy-Duty Boots','Adamant','Extreme Speed,Shadow Claw,Swords Dance,Recover');
add('Eternatus','Pressure','Black Sludge','Timid','Dynamax Cannon,Sludge Bomb,Flamethrower,Recover','special');
add('Rayquaza','Air Lock','Life Orb','Adamant','Dragon Ascent,Extreme Speed,Earthquake,Dragon Dance');
add('Mewtwo','Pressure','Life Orb','Timid','Psystrike,Ice Beam,Fire Blast,Nasty Plot','special');
add('Calyrex-Ice','As One (Glastrier)','Heavy-Duty Boots','Adamant','Glacial Lance,High Horsepower,Trick Room,Swords Dance');

const team=(id,names,overrides={})=>({id,team:names.map(n=>({...structuredClone(catalog[n]),...(overrides[n]||{})}))});
const profiles=[];
function profile(id,name,formatid,purpose,teams){profiles.push({id,name,formatid,purpose,teams,
 pair_indices:id==='ou-hidden-loadouts'?[[0,1],[0,3],[2,1],[2,3]]:[[0,1],[2,3]],
 scope:formatid==='gen9ou'?'mechanism stratum of Gen 9 OU; not an independent game':'different pinned Gen 9 singles ruleset'});}
profile('ou-hidden-loadouts','同物种多配置','gen9ou','检验从公开战况推断对手配置，避免物种名直接确定整套招式',[
 team('balanced-a',['Dragonite','Rotom-Wash','Scizor','Clefable','Garchomp','Greninja']),
 team('pivot-a',['Corviknight','Slowking','Meowscarada','Arcanine','Excadrill','Sylveon']),
 team('balanced-b',['Dragonite','Rotom-Wash','Scizor','Clefable','Garchomp','Greninja'],{
  Dragonite:{item:'Choice Band',moves:['Extreme Speed','Outrage','Earthquake','Fire Punch']},
  'Rotom-Wash':{item:'Choice Scarf',moves:['Hydro Pump','Thunderbolt','Volt Switch','Trick']},
  Scizor:{item:'Life Orb',moves:['Swords Dance','Bullet Punch','Close Combat','U-turn']},
  Clefable:{ability:'Unaware',moves:['Moonblast','Moonlight','Flamethrower','Calm Mind']},
  Garchomp:{item:'Choice Scarf',moves:['Earthquake','Outrage','Stone Edge','Fire Fang']},
  Greninja:{ability:'Torrent',item:'Choice Specs',moves:['Surf','Dark Pulse','Ice Beam','Water Shuriken']}}),
 team('pivot-b',['Corviknight','Slowking','Meowscarada','Arcanine','Excadrill','Sylveon'],{
  Corviknight:{item:'Rocky Helmet',moves:['Iron Defense','Body Press','Roost','Brave Bird']},
  Slowking:{item:'Leftovers',moves:['Surf','Future Sight','Slack Off','Chilly Reception']},
  Meowscarada:{item:'Choice Band',moves:['Flower Trick','Knock Off','U-turn','Triple Axel']},
  Arcanine:{item:'Life Orb',moves:['Flare Blitz','Extreme Speed','Close Combat','Crunch']},
  Excadrill:{ability:'Sand Rush',item:'Leftovers',moves:['Earthquake','Iron Head','Rapid Spin','Swords Dance']},
  Sylveon:{item:'Choice Specs',moves:['Hyper Voice','Shadow Ball','Psyshock','Quick Attack']}}),
]);
profile('ou-weather-cores','完整天气核心','gen9ou','保留天气发动者与受益者，检查天气时机、换人与队伍协同',[
 team('rain',['Pelipper','Barraskewda','Amoonguss','Scizor','Garchomp','Greninja']),
 team('sun',['Torkoal','Venusaur','Dragonite','Arcanine','Garchomp','Hatterene']),
 team('sand',['Tyranitar','Excadrill','Skarmory','Gastrodon','Gengar','Breloom'],{Excadrill:{ability:'Sand Rush'}}),
 team('snow',['Ninetales-Alola','Cetitan','Mamoswine','Corviknight','Slowking','Meowscarada']),
]);
profile('ou-hazards-pivot','场地控制与轮转','gen9ou','撒钉、清场、转场与回复；记录回合上限是否干扰评分',[
 team('hazards-a',['Garchomp','Skarmory','Gengar','Rotom-Wash','Clefable','Scizor']),
 team('pivot-a',['Corviknight','Excadrill','Slowking','Amoonguss','Meowscarada','Arcanine']),
 team('hazards-b',['Hippowdon','Toxapex','Gholdengo','Hydreigon','Sylveon','Mamoswine']),
 team('pivot-b',['Hatterene','Corviknight','Gastrodon','Rotom-Wash','Scizor','Greninja']),
]);
profile('ou-setup-denial','强化与反强化','gen9ou','选择强化窗口、识别 Unaware 与 Haze、避免无效堆叠',[
 team('setup-a',['Dragonite','Garchomp','Kingambit','Gholdengo','Clefable','Iron Valiant']),
 team('deny-a',['Dondozo','Skeledirge','Toxapex','Amoonguss','Skarmory','Meowscarada']),
 team('setup-b',['Salamence','Breloom','Excadrill','Hatterene','Venusaur','Greninja']),
 team('deny-b',['Clefable','Corviknight','Hippowdon','Slowking','Arcanine','Hydreigon'],{Clefable:{ability:'Unaware'}}),
]);
profile('gen9-monotype','同属性队伍','gen9monotype','单一共享属性带来的攻防覆盖限制；原生 Monotype 校验',[
 team('water',['Rotom-Wash','Slowking','Greninja','Pelipper','Barraskewda','Gastrodon'],{Pelipper:{item:'Heavy-Duty Boots'}}),
 team('steel',['Scizor','Corviknight','Excadrill','Skarmory','Iron Treads','Gholdengo'],{'Iron Treads':{item:'Leftovers'}}),
 team('flying',['Dragonite','Corviknight','Pelipper','Salamence','Skarmory','Talonflame'],{Pelipper:{item:'Heavy-Duty Boots'}}),
 team('dragon',['Dragonite','Garchomp','Salamence','Hydreigon','Dragapult','Goodra-Hisui']),
]);
profile('gen9-ubers','Ubers 单打','gen9ubers','更高强度的特性、场地、天气与优先级交互；原生 Ubers 校验',[
 team('sun-offense',['Koraidon','Groudon','Ho-Oh','Necrozma-Dusk-Mane','Arceus','Eternatus']),
 team('rain-special',['Dialga-Origin','Kyogre','Zacian-Crowned','Mewtwo','Rayquaza','Calyrex-Ice']),
 team('mixed-balance',['Dialga-Origin','Necrozma-Dusk-Mane','Ho-Oh','Arceus','Kyogre','Eternatus']),
 team('physical-pressure',['Koraidon','Zacian-Crowned','Groudon','Rayquaza','Mewtwo','Calyrex-Ice']),
]);

function capabilities(){
 const doubles=new Battle({formatid:'gen9doublesou',seed:[1,2,3,4],p1:{name:'p1',team:old[0].team},p2:{name:'p2',team:old[1].team}});
 doubles.choose('p1','team 123456');doubles.choose('p2','team 123456');
 const obs=observation(structuredClone(doubles.p1.activeRequest),extractChannelMessages(doubles.log.join('\n'),[1])[1],Dex.mod('gen9'));
 const doubleCheck={id:'gen9doublesou',status:'unsupported',active_slots:doubles.p1.activeRequest.active.length,
  generated_action_examples:obs.legal_actions.slice(0,3).map(a=>a.id),reason:'Current adapter reads active[0] only; it does not enumerate joint actions, target selection or per-slot forced switches.'};doubles.destroy();
 const randomTeam=Teams.generate('gen9randombattle',{seed:[1,2,3,4]});
 const randomCheck={id:'gen9randombattle',status:'unsupported_by_existing_runner',reason:'Existing buildBattle always validates a supplied fixed team; native random format rejects supplied teams.',
  validator_errors:new TeamValidator('gen9randombattle').validateTeam(structuredClone(randomTeam))};
 return [doubleCheck,randomCheck];
}
function generate(out){
 fs.mkdirSync(out,{recursive:false});const checks=[];
 for(const p of profiles){
  const errors=[];
  for(const t of p.teams){const e=new TeamValidator(p.formatid).validateTeam(structuredClone(t.team));if(e)errors.push({team:t.id,errors:e});}
  const ids=p.teams.flatMap(t=>t.team.map(m=>m.species)),sets=new Map();
  for(const t of p.teams)for(const m of t.team){if(!sets.has(m.species))sets.set(m.species,new Set());sets.get(m.species).add(JSON.stringify(m));}
  const entry={...p,legality_errors:errors,status:errors.length?'invalid_team':'legal',species:new Set(ids).size,
   multiple_loadout_species:[...sets].filter(([_,v])=>v.size>1).map(([s])=>s)};
  fs.writeFileSync(path.join(out,p.id+'.json'),JSON.stringify(entry,null,2)+'\n');checks.push({id:p.id,status:entry.status,errors});
 }
 fs.writeFileSync(path.join(out,'capabilities.json'),JSON.stringify(capabilities(),null,2)+'\n');
 fs.writeFileSync(path.join(out,'generation.json'),JSON.stringify(checks,null,2)+'\n');console.log(JSON.stringify(checks));
}
if(require.main===module)generate(path.resolve(process.argv[2]));
module.exports={profiles,capabilities};
