'use strict';
const {damage} = require('./common.cjs');
exports.chooseAction = o => {
  const moves = o.legal_actions.filter(a => a.kind === 'move' && !a.terastallize);
  if (!moves.length) return o.legal_actions[0].id;
  return moves.reduce((a, b) => damage(b.move, o.active, o.opponent) > damage(a.move, o.active, o.opponent) ? b : a).id;
};
