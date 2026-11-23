'use strict';
const fs=require('node:fs'),path=require('node:path'),readline=require('node:readline');
const {spawn,execFile}=require('node:child_process'),{performance}=require('node:perf_hooks');
const {create}=require('./engine.cjs');
const live=new Set();let sampling=false,monitorEnabled=true;
const monitor=setInterval(()=>{
  if (!monitorEnabled || sampling || !live.size) return;
  sampling=true;
  const workers=[...live].filter(p=>p.child.pid);
  execFile('/bin/ps',['-o','pid=,rss=','-p',workers.map(p=>p.child.pid).join(',')],(err,out)=>{
    sampling=false;
    if (err && workers.some(p=>live.has(p))) return workers.forEach(p=>p.fail('resource monitor unavailable'));
    for (const line of (out||'').trim().split('\n')) {
      const [pid,rss]=line.trim().split(/\s+/).map(Number);
      if (rss>512*1024) workers.find(p=>p.child.pid===pid)?.fail('memory limit');
    }
    for (const p of workers) {
      if (!live.has(p)) continue;
      let bytes=0,count=0;
      const visit=dir=>{for (const f of fs.readdirSync(dir,{withFileTypes:true})) {
        if (++count>512) throw Error('scratch file limit');
        const full=path.join(dir,f.name);
        if (f.isDirectory()) visit(full);
        else if (f.isFile()) bytes+=fs.statSync(full).size;
        if (bytes>16*1024**2) throw Error('scratch storage limit');
      }};
      try {visit(p.cwd);} catch(e) {p.fail(e.message);}
    }
  });
},250);monitor.unref();

class Policy {
  constructor(spec,limits) {
    this.limits=limits;this.cwd=spec.cwd;this.next=0;this.pending=null;this.failure=null;
    this.stderr='';this.bytes=0;this.wall=0;live.add(this);
    this.child=spawn(spec.command[0],spec.command.slice(1),{cwd:spec.cwd,env:{
      PATH:'/usr/bin:/bin',HOME:spec.cwd,TMPDIR:spec.cwd,LANG:'en_US.UTF-8'
    },stdio:['pipe','pipe','pipe']});
    this.closed=new Promise(resolve=>this.child.once('close',resolve));
    this.lines=readline.createInterface({input:this.child.stdout});
    this.lines.on('line',line=>{
      this.bytes+=Buffer.byteLength(line);
      if (this.bytes>1024**2) return this.fail('output limit');
      if (!this.pending) return this.fail('unsolicited output');
      try {
        const r=JSON.parse(line);
        if (r.id!==this.pending.id || !Number.isInteger(r.action)) throw Error('invalid response');
        const p=this.pending;this.pending=null;clearTimeout(p.timer);p.resolve(r.action);
      } catch(e) {this.fail(e.message);}
    });
    this.child.stderr.on('data',b=>{this.stderr+=b.toString();if(this.stderr.length>65536)this.fail('stderr limit');});
    this.child.on('error',e=>this.fail(e.message));
    this.child.on('exit',(code,sig)=>this.fail(`policy exited (${code}, ${sig})`));
    this.child.stdin.on('error',e=>this.fail(e.message));
  }
  fail(message) {
    this.failure ||= message;
    if(this.pending){const p=this.pending;this.pending=null;clearTimeout(p.timer);p.reject(Error(message));}
    this.child.kill('SIGKILL');
  }
  async choose(observation) {
    if(this.failure)throw Error(this.failure);
    const start=performance.now(),id=++this.next;
    const remaining=this.limits.cumulative_ms-this.wall;
    if(remaining<=0)throw Error('cumulative decision time limit');
    const budget=Math.min(remaining,id===1?this.limits.startup_ms:this.limits.action_ms);
    try {
      const action=await new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>this.fail('decision time limit'),budget);
        this.pending={id,resolve,reject,timer};
        this.child.stdin.write(JSON.stringify({id,observation})+'\n');
      });
      if(!observation.legal_actions.includes(action))throw Error('action is not legal');
      if(performance.now()-start>budget)throw Error('decision time limit');
      return action;
    } finally {this.wall+=performance.now()-start;}
  }
  async close(){live.delete(this);this.child.kill('SIGKILL');this.lines.close();await this.closed;}
}
async function play(scenario,worker,limits) {
  const start=performance.now(),engine=create(scenario.key),initial=engine.board(),steps=[];
  const p=new Policy(worker,limits);let error=null,termination='move_limit';
  try {
    for(let n=0;n<limits.max_steps;n++) {
      const obs=engine.observe(limits.max_steps);
      if(!obs.legal_actions.length){termination='game_over';break;}
      let action;
      try {action=await p.choose(obs);} catch(e) {error={message:e.message,stderr:p.stderr.slice(-2000)};termination='policy_failure';break;}
      // Engine exceptions are infrastructure failures, not candidate losses.
      steps.push(engine.step(action));
    }
    if(!error && !engine.observe(limits.max_steps).legal_actions.length)termination='game_over';
    const raw_score=engine.game.score;
    return {id:scenario.id,key:scenario.key,initial,steps,score:error?0:raw_score,raw_score,
      max_tile:Math.max(...engine.board()),moves:steps.length,termination,error,
      policy_ms:p.wall,wall_ms:performance.now()-start,max_steps:limits.max_steps};
  } finally {await p.close();}
}
function verify(record) {
  const engine=create(record.key),eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  if(!eq(engine.board(),record.initial))throw Error('initial board mismatch');
  if(record.steps.length>record.max_steps)throw Error('too many moves');
  for(const step of record.steps)if(!eq(engine.step(step.action),step))throw Error('trace mismatch');
  if(record.moves!==record.steps.length || record.raw_score!==engine.game.score || record.max_tile!==Math.max(...engine.board()))throw Error('final state mismatch');
  if(record.score!==(record.error?0:engine.game.score))throw Error('score mismatch');
  const legal=engine.observe(record.max_steps).legal_actions;
  if(record.termination==='game_over' && (legal.length || record.error))throw Error('invalid game-over');
  if(record.termination==='move_limit' && (!legal.length || record.moves!==record.max_steps || record.error))throw Error('invalid move limit');
  if(record.termination==='policy_failure' && !record.error)throw Error('missing failure');
  if(!['game_over','move_limit','policy_failure'].includes(record.termination))throw Error('unknown termination');
  return true;
}
async function main() {
  const mode=process.argv[2],input=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
  if(mode==='verify') {
    for(const file of input.files)verify(JSON.parse(fs.readFileSync(file,'utf8')));
    console.log(JSON.stringify({valid:true,checked:input.files.length}));return;
  }
  if(mode!=='batch')throw Error('expected batch or verify');
  monitorEnabled=!input.local;let next=0;
  async function worker() {
    while(next<input.scenarios.length) {
      const scenario=input.scenarios[next++];
      const result=await play(scenario,input.workers[scenario.id],input.limits);
      fs.writeFileSync(path.join(input.out,scenario.id+'.json'),JSON.stringify(result));
    }
  }
  await Promise.all(Array.from({length:input.concurrency},worker));
}
if(require.main===module)main().catch(e=>{for(const p of live)p.fail('batch aborted');console.error(e.stack);process.exitCode=1;});
module.exports={play,verify};
