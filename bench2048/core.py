from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=Path(__file__).resolve().parent
NODE=(ROOT/'.tools/node/bin/node').resolve()
BASELINE=PACKAGE/'policies/greedy'

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def digest(data):return hashlib.sha256(data).hexdigest()
def spec():return json.loads((PACKAGE/'spec.json').read_text())

def fingerprints():
    files=[p for p in PACKAGE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.cjs','.json','.html')]
    files += [ROOT/'2048/js'/n for n in ('tile.js','grid.js','game_manager.js')]+[NODE]
    files += [ROOT/'tasbench'/n for n in ('controller.py','development_exec.py','isolation.py','model_proxy.py','workspace_run.py','core.py') if (ROOT/'tasbench'/n).exists()]
    return {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(files)}

def scenarios(count,salt=None,excluded=()):
    if type(count)is not int or not 1<=count<=4096:raise ValueError('games must be 1..4096')
    excluded=set(excluded);rows=[];i=0
    while len(rows)<count:
        key=digest(f'2048-local/{salt}/{i}'.encode()) if salt is not None else secrets.token_hex(32)
        i+=1
        if key in excluded:continue
        excluded.add(key);rows.append({'id':f'game-{len(rows)+1:04d}','key':key})
    return rows

def freeze(source,dest):
    source=Path(source).absolute();dest=Path(dest)
    if not source.is_dir() or source.is_symlink():raise ValueError('policy must be an unlinked directory')
    paths=list(source.rglob('*'))
    if len(paths)>128:raise ValueError('too many submission files')
    total=0;contents={}
    for p in paths:
        if p.is_symlink() or (p.is_file() and p.stat().st_nlink>1):raise ValueError('linked submissions forbidden')
        if not p.is_file():continue
        if p.suffix not in ('.js','.cjs','.json','.txt'):raise ValueError('only JS/JSON/text submission files')
        data=p.read_bytes();total+=len(data)
        if total>2*1024**2:raise ValueError('submission exceeds 2 MiB')
        contents[p.relative_to(source)]=data
    if Path('player.cjs') not in contents:raise ValueError('missing player.cjs')
    dest.mkdir(parents=True,exist_ok=False)
    for name,data in contents.items():
        target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    return {str(n):digest(data) for n,data in sorted(contents.items())}

def bundle_hashes(folder):return {str(p.relative_to(folder)):digest(p.read_bytes()) for p in sorted(folder.rglob('*')) if p.is_file()}

def profile(bundle,scratch):
    q=lambda p:json.dumps(str(Path(p).resolve()))
    read=[Path('/System'),Path('/usr/lib'),Path('/Library/Apple'),Path(sys.base_prefix),NODE.parent.parent,bundle,scratch]
    literals=[PACKAGE/'policy_launcher.py',PACKAGE/'policy_worker.cjs']
    return '''(version 1)
(deny default)
(allow process-exec)
(allow signal (target self))
(allow file-read-metadata)
(allow file-read* '''+' '.join('(subpath '+q(p)+')' for p in read)+' '+ ' '.join('(literal '+q(p)+')' for p in literals)+'''
 (literal "/") (literal "/dev/null") (literal "/dev/random") (literal "/dev/urandom"))
(allow file-write* (subpath '''+q(scratch)+''') (literal "/dev/null"))
(deny file-link)
(allow sysctl-read)
(allow mach-lookup (global-name "com.apple.system.logger"))
'''

def worker(bundle,scratch,isolated):
    scratch.mkdir(parents=True)
    command=[str(Path(sys.executable).resolve()),'-I','-B',str(PACKAGE/'policy_launcher.py'),str(spec()['runtime']['cpu_seconds']),str(NODE),str(PACKAGE/'policy_worker.cjs'),str(bundle/'player.cjs')]
    if isolated:
        if sys.platform!='darwin':raise RuntimeError('official execution requires macOS Seatbelt')
        policy=scratch.parent/(scratch.name+'.sb');policy.write_text(profile(bundle,scratch))
        command=['/usr/bin/sandbox-exec','-f',str(policy),*command]
    return {'command':command,'cwd':str(scratch)}

def interval(values):
    rng=random.Random(1729);n=len(values)
    samples=sorted(sum(rng.choices(values,k=n))/n for _ in range(2000))
    return [samples[49],samples[1949]]

def aggregate(records):
    if not records:raise ValueError('empty result')
    values=[r['score'] for r in records];n=len(values)
    return {'games':n,'score':sum(values)/n,'score_ci95':interval(values),
      'failures':sum(bool(r['error']) for r in records),'move_limits':sum(r['termination']=='move_limit' for r in records),
      'mean_moves':sum(r['moves'] for r in records)/n,
      'tile_rates':{str(t):sum(not r['error'] and r['max_tile']>=t for r in records)/n for t in (512,1024,2048,4096,8192)},
      'max_tile_counts':{str(t):sum(r['max_tile']==t and not r['error'] for r in records) for t in sorted({r['max_tile'] for r in records})}}

def records(out):return [json.loads(p.read_text()) for p in sorted((Path(out)/'games').glob('game-*.json'))]
def public(result):return {k:result[k] for k in ('games','score','score_ci95','failures','move_limits','mean_moves','tile_rates','max_tile_counts')}

def paired(left,right):
    differences=[]
    for a,b in zip(left,right,strict=True):
        if (a['id'],a['key'])!=(b['id'],b['key']):raise ValueError('paired cases differ')
        differences.append(b['score']-a['score'])
    return {'score_delta':sum(differences)/len(differences),'paired_ci95':interval(differences),'games':len(differences)}

def evaluate(source,out,cases=None,isolated=True,timeout=600,concurrency=4):
    start=time.monotonic();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    hashes=freeze(Path(source),out/'candidate');cases=scenarios(spec()['training_games']) if cases is None else cases
    if not cases or len({s['id'] for s in cases})!=len(cases) or len({s['key'] for s in cases})!=len(cases):raise ValueError('empty/duplicate cases')
    import re
    if any(not re.fullmatch(r'game-\d{4}',s['id']) or not re.fullmatch(r'[a-f0-9]{64}',s['key']) for s in cases):raise ValueError('invalid scenario')
    save(out/'scenarios.json',cases);(out/'games').mkdir()
    workers={s['id']:worker(out/'candidate',out/'scratch'/s['id'],isolated) for s in cases}
    save(out/'batch.json',{'scenarios':cases,'workers':workers,'out':str(out/'games'),'limits':spec()['runtime'],'concurrency':concurrency,'local':not isolated})
    before=os.times()
    own_group=isolated and os.environ.get('BENCH2048_JUDGE')!='1'
    with (out/'engine.stdout').open('w') as stdout,(out/'engine.stderr').open('w') as stderr:
        p=subprocess.Popen([str(NODE),str(PACKAGE/'runner.cjs'),'batch',str(out/'batch.json')],env={'PATH':'/usr/bin:/bin','LANG':'en_US.UTF-8'},stdout=stdout,stderr=stderr,start_new_session=own_group)
        try:p.wait(timeout=timeout)
        finally:
            try:
                if own_group:os.killpg(p.pid,signal.SIGKILL)
                elif p.poll() is None:p.kill()
            except ProcessLookupError:pass
            p.wait()
    if p.returncode:raise RuntimeError('engine runner failed: '+(out/'engine.stderr').read_text()[-2000:])
    rows=records(out)
    if [r['id'] for r in rows]!=sorted(s['id'] for s in cases):raise RuntimeError('incomplete batch')
    after=os.times();result=aggregate(rows)
    result.update(protocol=spec()['protocol'],candidate_hashes=hashes,provenance=fingerprints(),isolated=isolated,
        scenarios_sha256=digest((out/'scenarios.json').read_bytes()),
        records_sha256={p.name:digest(p.read_bytes()) for p in sorted((out/'games').glob('*.json'))},
        wall_seconds=time.monotonic()-start,cpu_seconds=after.children_user+after.children_system-before.children_user-before.children_system)
    save(out/'result.json',result)
    from .report import render_batch
    render_batch(out,rows,result)
    return result

def verify(out):
    out=Path(out).resolve();r=json.loads((out/'result.json').read_text())
    if r['provenance']!=fingerprints():raise ValueError('evaluator provenance changed')
    if bundle_hashes(out/'candidate')!=r['candidate_hashes']:raise ValueError('candidate changed')
    if digest((out/'scenarios.json').read_bytes())!=r['scenarios_sha256']:raise ValueError('scenarios changed')
    rows=records(out);cases=json.loads((out/'scenarios.json').read_text())
    if {p.name:digest(p.read_bytes()) for p in sorted((out/'games').glob('*.json'))}!=r['records_sha256']:raise ValueError('records changed')
    if sorted((x['id'],x['key']) for x in rows)!=sorted((x['id'],x['key']) for x in cases):raise ValueError('case/record mismatch')
    if any(x['max_steps']!=spec()['runtime']['max_steps'] for x in rows):raise ValueError('game limits changed')
    if any(r[k]!=v for k,v in aggregate(rows).items()):raise ValueError('score changed')
    save(out/'verify-input.json',{'files':[str(out/'games'/n) for n in sorted(r['records_sha256'])]})
    raw=subprocess.check_output([str(NODE),str(PACKAGE/'runner.cjs'),'verify',str(out/'verify-input.json')],text=True,timeout=180)
    response=json.loads(raw);save(out/'verification.json',response);return response
