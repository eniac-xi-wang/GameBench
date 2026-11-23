'use strict';
// Reproducible policy-side randomness, independent of the game's private stream.
let state=271828183;
exports.chooseAction=o=>{
  state^=state<<13;state^=state>>>17;state^=state<<5;
  return o.legal_actions[(state>>>0)%o.legal_actions.length];
};
