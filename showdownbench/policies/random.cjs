'use strict';
// Local policy randomness is independent of battle randomness; reproducible per match.
let state = 123456789;
exports.chooseAction = o => {
  state ^= state << 13; state ^= state >>> 17; state ^= state << 5;
  const actions = o.legal_actions.filter(a => !a.terastallize);
  const moves = actions.filter(a => a.kind === 'move');
  const pool = moves.length ? moves : actions;
  return pool[(state >>> 0) % pool.length].id;
};
