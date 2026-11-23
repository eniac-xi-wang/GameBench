'use strict';
const {Dex} = require(process.env.SHOWDOWN_ROOT + '/dist/sim');
const dex = Dex.mod('gen9');
function multiplier(type, target) {
  if (!target) return 1;
  if (!dex.getImmunity(type, target.types)) return 0;
  return 2 ** dex.getEffectiveness(type, target.types);
}
function damage(move, own, foe) {
  if (move.category === 'Status') return 0;
  const special = move.category === 'Special', atk = special ? 'spa' : 'atk', def = special ? 'spd' : 'def';
  const power = move.basePower || (move.id === 'lowkick' || move.id === 'grassknot' ? 80 : 0);
  const stat = own?.stats?.[atk] || own?.base_stats?.[atk] || 100;
  const defense = 2 * (foe?.base_stats?.[def] || 100) + 36;
  const stage = own?.boosts?.[atk] || 0;
  const boost = stage >= 0 ? (2 + stage) / 2 : 2 / (2 - stage);
  const stab = own?.types?.includes(move.type) ? 1.5 : 1;
  return power * stat / defense * boost * stab * multiplier(move.type, foe) * (move.accuracy === true ? 1 : move.accuracy / 100);
}
module.exports = {dex, damage, multiplier};
