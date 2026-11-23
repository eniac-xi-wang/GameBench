'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), crypto = require('node:crypto');
const {slide} = require('./rules.cjs');
const gameRoot = path.resolve(__dirname, '../2048');
const sources = ['tile.js','grid.js','game_manager.js'].map(n => fs.readFileSync(path.join(gameRoot,'js',n),'utf8')).join('\n');

// 256-bit private key, one independently indexed HMAC block per draw. The policy
// process never receives the key, this function, or the live engine instance.
function randomStream(key) {
  if (!/^[a-f0-9]{64}$/.test(key)) throw Error('scenario key must be 256-bit hex');
  let counter = 0;
  return () => {
    const b = crypto.createHmac('sha256',Buffer.from(key,'hex')).update('2048-v1/'+counter++).digest();
    return b.readUIntBE(0,6)/281474976710656;
  };
}
function create(key) {
  const rng = randomStream(key), math = Object.create(Math); math.random = rng;
  const ctx = vm.createContext({Math:math}); vm.runInContext(sources,ctx);
  const Input = function() {}; Input.prototype.on = function() {};
  const Actuator = function() {}; Actuator.prototype.actuate = function() {}; Actuator.prototype.continueGame = function() {};
  const Storage = function() {};
  Storage.prototype.getGameState = () => null; Storage.prototype.getBestScore = () => 0;
  for (const n of ['setGameState','setBestScore','clearGameState']) Storage.prototype[n] = function() {};
  const game = new ctx.GameManager(4,Input,Actuator,Storage);
  game.keepPlaying = true; // Fixed task rule: continue beyond reaching 2048.
  const board = () => Array.from({length:16},(_,i) => game.grid.cells[i%4][Math.floor(i/4)]?.value || 0);
  let steps = 0;
  return {
    game, board,
    observe(maxSteps) {
      const b=board();
      return {board:b,score:game.score,step:steps,max_steps:maxSteps,
        legal_actions:[0,1,2,3].filter(a => slide(b,a).changed)};
    },
    step(action) {
      const before=board(), expected=slide(before,action), score=game.score;
      if (!expected.changed) throw Error('ineffective move');
      game.move(action);steps++;
      const after=board(), added=[];
      for (let i=0;i<16;i++) if (after[i]!==expected.board[i]) added.push(i);
      if (game.score-score!==expected.gain || added.length!==1 || expected.board[added[0]]!==0 || ![2,4].includes(after[added[0]]))
        throw Error('original engine / legal-action helper disagree');
      return {action,board:after,score:game.score,spawn:{index:added[0],value:after[added[0]]}};
    }
  };
}
module.exports = {create,randomStream,slide};
