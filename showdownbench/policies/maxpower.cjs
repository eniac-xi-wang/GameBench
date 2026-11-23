'use strict';
exports.chooseAction = o => {
  const moves = o.legal_actions.filter(a => a.kind === 'move' && !a.terastallize);
  if (!moves.length) return o.legal_actions[0].id;
  return moves.reduce((a, b) => b.move.basePower > a.move.basePower ? b : a).id;
};
