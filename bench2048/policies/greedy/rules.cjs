'use strict';
// Row-major, deterministic slide only. No random tile is inserted here.
function slide(board, direction) {
  if (!Number.isInteger(direction) || direction < 0 || direction > 3) throw Error('invalid direction');
  const out = board.slice(); let gain = 0;
  for (let lane = 0; lane < 4; lane++) {
    const ids = Array.from({length:4}, (_, k) => direction === 0 ? k*4+lane :
      direction === 1 ? lane*4+3-k : direction === 2 ? (3-k)*4+lane : lane*4+k);
    const values = ids.map(i => board[i]).filter(Boolean), merged = [];
    for (let i = 0; i < values.length; i++) {
      if (values[i] === values[i+1]) {const v = values[i]*2; merged.push(v); gain += v; i++;}
      else merged.push(values[i]);
    }
    ids.forEach((id,k) => out[id] = merged[k] || 0);
  }
  return {board:out, gain, changed:out.some((v,i) => v !== board[i])};
}
module.exports = {slide};
