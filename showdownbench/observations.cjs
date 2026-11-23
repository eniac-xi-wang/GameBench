'use strict';
// Only player-visible protocol lines and that player's own request enter here.
function condition(text = '') {
  const [hp, status] = text.split(' '), [a, b] = hp.split('/').map(Number);
  return {hp_fraction: b ? a / b : a === 0 ? 0 : null, status: status || '', fainted: text.includes('fnt')};
}
function speciesOf(details) { return details.split(',')[0]; }
function legalActions(request, dex) {
  if (!request || request.wait) return [];
  const team = request.side.pokemon;
  if (request.teamPreview) return team.map((p, i) => ({
    id: 'team ' + [i + 1, ...team.map((_, j) => j + 1).filter(j => j !== i + 1)].join(''),
    kind: 'lead', slot: i + 1,
  }));
  const actions = [];
  const active = request.active?.[0];
  if (!request.forceSwitch && active) {
    for (const [i, move] of active.moves.entries()) {
      if (move.disabled) continue;
      const data = dex.moves.get(move.id || move.move);
      const m = {};
      for (const k of ['id','name','type','category','basePower','accuracy','priority','target','flags',
        'boosts','heal','recoil','drain','status','secondary','secondaries','self','sideCondition','multihit']) {
        if (data[k] !== undefined) m[k] = data[k];
      }
      actions.push({id: `move ${i + 1}`, kind: 'move', slot: i + 1, move: m, pp: move.pp});
      if (active.canTerastallize) actions.push({...actions.at(-1), id: `move ${i + 1} terastallize`, terastallize: active.canTerastallize});
    }
  }
  if (request.forceSwitch || !active?.trapped) {
    for (const [i, p] of team.entries()) {
      if (!p.active && !p.condition.endsWith(' fnt')) actions.push({id: `switch ${i + 1}`, kind: 'switch', slot: i + 1});
    }
  }
  return actions;
}
function observation(request, history, dex) {
  const side = request.side.id, foe = side === 'p1' ? 'p2' : 'p1';
  const publicState = {p1: {team: [], active: null, conditions: {}}, p2: {team: [], active: null, conditions: {}}};
  let turn = 0, weather = '', terrain = '';
  for (const line of history) {
    const p = line.split('|'), kind = p[1];
    if (kind === 'turn') turn = Number(p[2]);
    if (kind === '-weather') weather = p[2];
    if (kind === '-fieldstart') terrain = p[2];
    if (kind === '-fieldend' && p[2] === terrain) terrain = '';
    if (kind === 'poke' && publicState[p[2]]) publicState[p[2]].team.push({species: speciesOf(p[3]), details: p[3]});
    const s = publicState[p[2]?.slice(0, 2)];
    if (!s) continue;
    if (kind === 'switch' || kind === 'drag' || kind === 'replace') {
      s.active = {ident: p[2], species: speciesOf(p[3]), details: p[3], ...condition(p[4]), boosts: {}, revealed_moves: []};
    } else if (s.active && p[2] === s.active.ident) {
      if (kind === '-damage' || kind === '-heal') Object.assign(s.active, condition(p[3]));
      if (kind === 'faint') Object.assign(s.active, {hp_fraction: 0, fainted: true});
      if (kind === '-status') s.active.status = p[3];
      if (kind === '-curestatus') s.active.status = '';
      if (kind === '-boost' || kind === '-unboost') s.active.boosts[p[3]] = (s.active.boosts[p[3]] || 0) + Number(p[4]) * (kind === '-boost' ? 1 : -1);
      if (kind === '-setboost') s.active.boosts[p[3]] = Number(p[4]);
      if (kind === '-clearboost') s.active.boosts = {};
      if (kind === 'move') s.active.revealed_moves.push(p[3]);
      if (kind === '-ability') s.active.ability = p[3];
      if (kind === '-item') s.active.item = p[3];
      if (kind === '-terastallize') s.active.tera_type = p[3];
    }
    if (kind === '-sidestart') s.conditions[p[3]] = true;
    if (kind === '-sideend') delete s.conditions[p[3]];
  }
  const enrich = p => {
    const d = dex.species.get(p.species || speciesOf(p.details));
    return {...p, species: d.name, types: p.tera_type ? [p.tera_type] : d.types, base_stats: d.baseStats};
  };
  const own = request.side.pokemon.map(p => enrich({...p, ...condition(p.condition)}));
  const active = own.find(p => p.active);
  if (active) Object.assign(active, {boosts: publicState[side].active?.boosts || {}, tera_type: publicState[side].active?.tera_type});
  if (active?.tera_type) active.types = [active.tera_type];
  return {version: 1, side, turn, request, legal_actions: legalActions(request, dex),
    own_team: own, active, opponent: publicState[foe].active ? enrich(publicState[foe].active) : null,
    opponent_preview: publicState[foe].team.map(enrich), weather, terrain,
    own_side_conditions: publicState[side].conditions, opponent_side_conditions: publicState[foe].conditions, history};
}
module.exports = {observation, legalActions};
