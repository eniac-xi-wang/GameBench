'use strict';
const {slide}=require('./rules.cjs');
exports.chooseAction=o=>{
  let best=o.legal_actions[0], value=-Infinity;
  for (const a of o.legal_actions) {
    const r=slide(o.board,a);
    const v=r.gain*100+r.board.filter(x=>x===0).length;
    if (v>value) {value=v;best=a;}
  }
  return best;
};
