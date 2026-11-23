from __future__ import annotations
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=Path(__file__).resolve().parent
NODE=(ROOT/'.tools/node/bin/node').resolve()
BASELINE=PACKAGE/'baselines'

def digest(data):return hashlib.sha256(data).hexdigest()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def spec():return json.loads((PACKAGE/'spec.json').read_text())
def tasks():return [json.loads(p.read_text()) for p in sorted((PACKAGE/'tasks').glob('*.json'))]
def fingerprints():
    files=[p for p in PACKAGE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.cjs','.js','.json','.html')]
    files+=[NODE]+[ROOT/'tasbench'/n for n in ('controller.py','development_exec.py','isolation.py','model_proxy.py','workspace_run.py','core.py') if (ROOT/'tasbench'/n).exists()]
    manifest=json.loads((PACKAGE/'vendor/manifest.json').read_text())
    files+=[ROOT/'shapez/src/js'/name for name in manifest['inputs']]
    return {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(set(files))}
def bundle_hashes(source):return {p.name:digest(p.read_bytes()) for p in sorted(Path(source).glob('*.json'))}
def freeze(source,dest):
    source=Path(source).absolute();dest=Path(dest)
    if not source.is_dir() or source.is_symlink():raise ValueError('candidate must be an unlinked directory')
    expected={t['id']+'.json' for t in tasks()};found={p.name for p in source.iterdir()}
    if found!=expected:raise ValueError('candidate must contain exactly one JSON blueprint per task: '+', '.join(sorted(expected)))
    contents={}
    for name in sorted(expected):
        p=source/name
        if p.is_symlink() or not p.is_file() or p.stat().st_nlink>1:raise ValueError('linked or non-file candidate')
        data=p.read_bytes()
        if len(data)>256*1024:raise ValueError('blueprint exceeds 256 KiB')
        # No executable submitted code ever enters the authoritative judge.
        value=json.loads(data,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('non-finite JSON')))
        json.dumps(value,allow_nan=False)  # Also reject exponent overflow such as 1e400.
        contents[name]=data
    dest.mkdir(parents=True,exist_ok=False)
    for name,data in contents.items():(dest/name).write_bytes(data)
    return bundle_hashes(dest)
def run(cases,replay=True,timeout=30):
    def limits():
        resource.setrlimit(resource.RLIMIT_CPU,(20,20))
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    result=subprocess.run([str(NODE),'--max-old-space-size=256',str(PACKAGE/'runner.cjs')],
       input=json.dumps({'cases':cases,'replay':replay}),text=True,capture_output=True,timeout=timeout,
       env={'PATH':'/usr/bin:/bin','LANG':'en_US.UTF-8'},cwd=PACKAGE,preexec_fn=limits)
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    if result.returncode:raise RuntimeError('simulation failed: '+result.stderr[-2000:])
    return json.loads(result.stdout),after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
def public(result):return {k:result[k] for k in ('score','failures','total_cost','tasks')}
def evaluate(source,out,timeout=30):
    start=time.monotonic();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    hashes=freeze(source,out/'candidate');definitions=tasks();save(out/'tasks.json',definitions)
    cases=[{'task':t,'blueprint':json.loads((out/'candidate'/(t['id']+'.json')).read_text())} for t in definitions]
    records,cpu=run(cases,timeout=timeout)
    for r in records:save(out/'records'/(r['task_id']+'.json'),r)
    summaries=[{k:v for k,v in r.items() if k not in ('layout','deliveries','frames')} for r in records]
    result={'score':sum(r['score'] for r in records)/len(records),'failures':sum(not r['valid'] for r in records),
      'total_cost':sum(r.get('build_cost',0) for r in records),'tasks':summaries,'candidate_hashes':hashes,
      'provenance':fingerprints(),'task_sha256':digest((out/'tasks.json').read_bytes()),
      'record_sha256':{p.name:digest(p.read_bytes()) for p in sorted((out/'records').glob('*.json'))},
      'cpu_seconds':cpu,'wall_seconds':time.monotonic()-start,'protocol':spec()['protocol']}
    save(out/'result.json',result)
    from .report import render
    render(out,definitions,records,result)
    return result
def verify(out):
    out=Path(out);result=json.loads((out/'result.json').read_text())
    if result['provenance']!=fingerprints():raise ValueError('evaluator or upstream sources changed')
    if result['candidate_hashes']!=bundle_hashes(out/'candidate'):raise ValueError('candidate changed')
    if result['task_sha256']!=digest((out/'tasks.json').read_bytes()):raise ValueError('tasks changed')
    if result['record_sha256']!={p.name:digest(p.read_bytes()) for p in sorted((out/'records').glob('*.json'))}:raise ValueError('records changed')
    definitions=json.loads((out/'tasks.json').read_text())
    if definitions!=tasks():raise ValueError('task definitions differ')
    fresh,_=run([{'task':t,'blueprint':json.loads((out/'candidate'/(t['id']+'.json')).read_text())} for t in definitions])
    for r in fresh:
        if r!=json.loads((out/'records'/(r['task_id']+'.json')).read_text()):raise ValueError('deterministic replay mismatch')
    if result['score']!=sum(r['score'] for r in fresh)/len(fresh):raise ValueError('score changed')
    if result['failures']!=sum(not r['valid'] for r in fresh):raise ValueError('failure count changed')
    if result['total_cost']!=sum(r.get('build_cost',0) for r in fresh):raise ValueError('build cost changed')
    summaries=[{k:v for k,v in r.items() if k not in ('layout','deliveries','frames')} for r in fresh]
    if result['tasks']!=summaries:raise ValueError('task summaries changed')
    checked={'valid':True,'tasks':len(fresh),'frames':sum(len(r.get('frames',[])) for r in fresh),
      'method':'fresh original-engine simulation, comparing every delivery and replay snapshot'}
    save(out/'verification.json',checked);return checked
