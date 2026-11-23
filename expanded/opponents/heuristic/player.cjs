'use strict';
const {dex, damage, multiplier} = require('./common.cjs');
let lastSwitch = -100;
exports.chooseAction = o => {
  const actions = o.legal_actions.filter(a => !a.terastallize);
  function score(a) {
    const p = o.own_team[a.slot - 1];
    if (a.kind === 'lead') return p.base_stats.spe + p.base_stats.atk + p.base_stats.spa;
    if (a.kind === 'switch') {
      const best = Math.max(...p.moves.map(m => damage(dex.moves.get(m), p, o.opponent)), 0);
      const incoming = Math.max(...(o.opponent?.types || []).map(t => multiplier(t, p)), 1);
      return best * .5 - 35 * incoming + (p.hp_fraction || 0) * 15 - (o.turn - lastSwitch <= 2 ? 90 : 15);
    }
    const m = a.move;
    let v = damage(m, o.active, o.opponent);
    if (m.heal && o.active.hp_fraction < .5) v = 95;
    if (m.boosts && m.target === 'self' && o.active.hp_fraction > .65 &&
        Object.entries(m.boosts).some(([k, b]) => b > 0 && (o.active.boosts[k] || 0) < 2)) v = 65;
    if (m.status && !o.opponent?.status) v = m.status === 'par' ? 45 : 35;
    if (m.sideCondition && !o.opponent_side_conditions['move: ' + m.name]) v = 45;
    if (o.opponent && o.opponent.hp_fraction < .25 && m.priority > 0) v *= 1.6;
    return v;
  }
  const best = actions.reduce((a, b) => score(b) > score(a) ? b : a);
  if (best.kind === 'switch') lastSwitch = o.turn;
  return best.id;
};
