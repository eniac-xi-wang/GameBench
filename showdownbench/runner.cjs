'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const readline = require('node:readline');
const {spawn, execFile} = require('node:child_process');
const {performance} = require('node:perf_hooks');
const game = path.resolve(__dirname, '../pokemon-showdown');
const {Battle, Dex, TeamValidator} = require(game + '/dist/sim');
const {extractChannelMessages} = require(game + '/dist/sim/battle');
const {observation} = require('./observations.cjs');
const dex = Dex.mod('gen9');
const hash = x => crypto.createHash('sha256').update(typeof x === 'string' ? x : JSON.stringify(x)).digest('hex');
const normalize = lines => lines.filter(l => !l.startsWith('|t:|'));
const live = new Set();
let sampling = false;
let monitorResources = true;
const monitor = setInterval(() => {
  if (!monitorResources || sampling || !live.size) return;
  sampling = true;
  const policies = [...live].filter(p => p.child.pid);
  execFile('/bin/ps', ['-o','pid=,rss=','-p',policies.map(p => p.child.pid).join(',')], (err, output) => {
    sampling = false;
    for (const line of (output || '').trim().split('\n')) {
      const [pid,rss] = line.trim().split(/\s+/).map(Number);
      if (rss > 512 * 1024) policies.find(p => p.child.pid === pid)?.fail('policy memory limit');
    }
    for (const p of policies) {
      let total = 0, count = 0;
      const visit = dir => {for (const f of fs.readdirSync(dir,{withFileTypes:true})) {
        if (++count > 512) throw Error('policy storage file limit');
        const file = path.join(dir,f.name);
        if (f.isDirectory()) visit(file);
        else if (f.isFile()) {total += fs.statSync(file).size;if (total > 32 * 1024**2) throw Error('policy storage limit');}
      }};
      try {visit(p.cwd);} catch(e) {p.fail(e.message);}
    }
  });
}, 250);
monitor.unref();

class Policy {
  constructor(spec) {
    this.cwd = spec.cwd; live.add(this);
    this.next = 0; this.pending = null; this.stderr = ''; this.bytes = 0; this.wall = 0; this.failure = null;
    this.child = spawn(spec.command[0], spec.command.slice(1), {cwd: spec.cwd, env: {
      PATH: '/usr/bin:/bin', HOME: spec.cwd, TMPDIR: spec.cwd, LANG: 'en_US.UTF-8',
      SHOWDOWN_ROOT: game,
    }, stdio: ['pipe','pipe','pipe']});
    this.lines = readline.createInterface({input: this.child.stdout});
    this.lines.on('line', line => {
      this.bytes += line.length;
      if (this.bytes > 1024 * 1024) return this.fail('policy output limit');
      if (!this.pending) return this.fail('unsolicited policy output');
      try {
        const r = JSON.parse(line);
        if (r.id !== this.pending.id || typeof r.action !== 'string') throw Error('invalid policy response');
        const p = this.pending; this.pending = null; clearTimeout(p.timer); p.resolve(r.action);
      } catch (e) { this.fail(e.message); }
    });
    this.child.stderr.on('data', x => {
      this.stderr += x.toString();
      if (this.stderr.length > 65536) this.fail('policy stderr limit');
    });
    this.child.on('error', e => this.fail(e.message));
    this.child.on('exit', (code, sig) => this.fail(`policy exited (${code}, ${sig})`));
    this.child.stdin.on('error', e => this.fail(e.message));
  }
  fail(message) {
    this.failure ||= message;
    if (this.pending) {const p = this.pending; this.pending = null; clearTimeout(p.timer); p.reject(Error(message));}
    this.child.kill('SIGKILL');
  }
  async choose(obs) {
    if (this.failure) throw Error(this.failure);
    const start = performance.now(), id = ++this.next;
    try {
      const action = await new Promise((resolve, reject) => {
        const timer = setTimeout(() => this.fail('decision time limit'), id === 1 ? 5000 : 1000);
        this.pending = {resolve, reject, timer, id};
        this.child.stdin.write(JSON.stringify({id, observation: obs}) + '\n');
      });
      if (!obs.legal_actions.some(a => a.id === action)) throw Error('action not in legal_actions');
      return action;
    } finally {
      this.wall += performance.now() - start;
      if (this.wall > 30000) this.fail('cumulative decision time limit');
    }
  }
  close() { live.delete(this); this.child.kill('SIGKILL'); this.lines.close(); }
}

function buildBattle(config) {
  for (const team of [config.team1, config.team2]) {
    const errors = new TeamValidator(config.formatid).validateTeam(structuredClone(team));
    if (errors) throw Error('Invalid fixed team: ' + errors.join('; '));
  }
  return new Battle({formatid: config.formatid, seed: config.seed,
    p1: {name:'p1', team:structuredClone(config.team1)}, p2: {name:'p2',team:structuredClone(config.team2)}});
}
function finishRecord(battle, scenario, actions, termination, errors, policyMs, elapsed) {
  const log = normalize(extractChannelMessages(battle.log.join('\n'), [0])[0]);
  const winner = battle.winner || null;
  const completed = termination !== 'turn_limit' && termination !== 'engine_stalled';
  const score = errors[scenario.candidate_side] ? 0 : completed ? winner === scenario.candidate_side ? 1 : winner ? 0 : .5 : 0;
  return {id:scenario.id, block:scenario.block, opponent:scenario.opponent, candidate_side:scenario.candidate_side,
    team_ids:scenario.team_ids, winner, score, turns:battle.turn, termination, errors,
    policy_ms:policyMs, wall_ms:elapsed, log, log_sha256:hash(log), actions,
    config:{formatid:scenario.formatid,seed:scenario.seed,team1:scenario.team1,team2:scenario.team2},
    engine_commit:scenario.engine_commit};
}
async function play(scenario, workers) {
  const start = performance.now(), battle = buildBattle(scenario), actions = [], errors = {};
  const p = {p1:new Policy(workers.p1),p2:new Policy(workers.p2)};
  let termination = 'completed';
  try {
    for (let iteration = 0; !battle.ended; iteration++) {
      if (battle.turn > 200 || iteration > 1200) {termination = 'turn_limit'; break;}
      const channels = extractChannelMessages(battle.log.join('\n'), [1,2]);
      const active = battle.sides.filter(s => s.activeRequest && !s.activeRequest.wait && !s.isChoiceDone());
      if (!active.length) {termination = 'engine_stalled'; break;}
      const replies = await Promise.all(active.map(async side => {
        const obs = observation(structuredClone(side.activeRequest), normalize(channels[Number(side.id[1])]), dex);
        try {return {side:side.id, action:await p[side.id].choose(obs)};}
        catch (e) {return {side:side.id,error:e.message,stderr:p[side.id].stderr.slice(-2000)};}
      }));
      const failed = replies.filter(r => r.error);
      if (failed.length) {
        for (const r of failed) errors[r.side] = {message:r.error,stderr:r.stderr};
        termination = 'policy_failure';
        const winner = failed.length === 2 ? null : failed[0].side === 'p1' ? 'p2' : 'p1';
        actions.push({forfeit:failed.map(r => r.side),winner}); battle.win(winner); break;
      }
      for (const r of replies) {
        actions.push({turn:battle.turn,side:r.side,action:r.action});
        if (!battle.choose(r.side,r.action)) {
          // An unavailable action can reveal a previously hidden trapping ability.
          // Repeat from the engine's corrected request, exactly as a normal client would.
          const side = battle.getSide(r.side);
          if (side.choice.error?.startsWith("Can't switch: The active Pokémon is trapped")) continue;
          throw Error('Legal action rejected by engine: ' + side.choice.error);
        }
      }
    }
    return finishRecord(battle, scenario, actions, termination, errors,
      {p1:p.p1.wall,p2:p.p2.wall}, performance.now() - start);
  } finally {p.p1.close();p.p2.close();battle.destroy();}
}
function replay(record) {
  const battle = buildBattle(record.config);
  for (const action of record.actions) {
    if (action.forfeit) battle.win(action.winner);
    else if (!battle.choose(action.side, action.action) && !battle.getSide(action.side).choice.error?.includes('trapped')) throw Error('Replay rejected action');
  }
  const log = normalize(extractChannelMessages(battle.log.join('\n'), [0])[0]);
  const result = {valid:hash(log) === record.log_sha256 && (battle.winner || null) === record.winner && battle.turn === record.turns,
    log_sha256:hash(log),winner:battle.winner || null,turns:battle.turn};
  battle.destroy(); return result;
}
async function main() {
  const mode = process.argv[2], input = JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
  monitorResources = !input.local;
  if (mode === 'verify') {
    let checked = 0;
    for (const file of input.files) {const result = replay(JSON.parse(fs.readFileSync(file))); if (!result.valid) throw Error('Replay mismatch: '+file); checked++;}
    console.log(JSON.stringify({valid:true,checked})); return;
  }
  if (mode !== 'batch') throw Error('Use batch or verify');
  let next = 0;
  async function worker() {
    while (next < input.scenarios.length) {
      const s = input.scenarios[next++], candidate = input.policies.candidate, opponent = input.policies[s.opponent];
      const result = await play(s, input.workers?.[s.id] || (s.candidate_side === 'p1' ? {p1:candidate,p2:opponent} : {p1:opponent,p2:candidate}));
      fs.writeFileSync(path.join(input.out,s.id+'.json'),JSON.stringify(result));
      console.log(JSON.stringify({id:s.id,score:result.score,turns:result.turns,termination:result.termination}));
    }
  }
  await Promise.all(Array.from({length:input.concurrency || 2},worker));
}
if (require.main === module) main().catch(e => {console.error(e.stack);process.exitCode=1;});
module.exports = {buildBattle,replay};
