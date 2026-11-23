from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'pokemon-showdown'
NODE = (ROOT / '.tools/node/bin/node').resolve()
POLICIES = ROOT / 'showdownbench/policies'
OPPONENTS = ['maxpower', 'damage', 'heuristic']


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fingerprints():
    files = list((ROOT / 'showdownbench').glob('*.py')) + list((ROOT / 'showdownbench').glob('*.cjs'))
    files += list(POLICIES.glob('*.cjs')) + [ROOT / 'showdownbench/data/teams.json']
    # Runtime modules, not just git HEAD, establish the actual engine being executed.
    files += list((GAME / 'dist').rglob('*.js')) + list((GAME / 'dist').rglob('*.json'))
    files += list((GAME/'node_modules/ts-chacha20').rglob('*.js'))
    files += [GAME / 'package-lock.json', GAME/'package.json', NODE]
    return {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in sorted(files)}


def make_suite(repeats=2, salt='showdown-dev-v1', heldout=False):
    teams = json.loads((ROOT / 'showdownbench/data/teams.json').read_text())
    if heldout:
        a = {'id':'heldout-mix-a', 'team':[teams[i % 4]['team'][i] for i in range(6)]}
        b = {'id':'heldout-mix-b', 'team':[teams[(i + 2) % 4]['team'][i] for i in range(6)]}
        pairs = [(a,teams[0]),(b,teams[1]),(teams[2],a),(teams[3],b)]
    else:
        pairs = [(teams[i],teams[(i+1)%4]) for i in range(4)]
    commit = subprocess.check_output(['git','-C',str(GAME),'rev-parse','HEAD'],text=True).strip() if (GAME/'.git').exists() else '965a535ef892d13cd68cf75c076db26f9f32842a'
    rows=[]
    for opponent in OPPONENTS:
        for pair_id, (a,b) in enumerate(pairs):
            for r in range(repeats):
                block=f'{opponent}-{pair_id}-{r}'
                seed='sodium,'+digest(f'{salt}/{block}'.encode())[:32]
                for own,foe in ((a,b),(b,a)):
                    for side in ('p1','p2'):
                        rows.append(dict(id=f'game-{len(rows)+1:04d}',block=block,opponent=opponent,
                            formatid='gen9ou',seed=seed,engine_commit=commit,candidate_side=side,
                            team_ids=[own['id'],foe['id']] if side=='p1' else [foe['id'],own['id']],
                            team1=own['team'] if side=='p1' else foe['team'],team2=foe['team'] if side=='p1' else own['team']))
    return rows


def freeze_bundle(source: Path, dest: Path):
    source=source.absolute()
    if source.is_symlink():raise ValueError('symlink policy is forbidden')
    files=list(source.rglob('*')) if source.is_dir() else [source]
    if len(files)>128:raise ValueError('submission has too many files')
    dest.mkdir(parents=True,exist_ok=False)
    total=0; hashes={}
    for p in files:
        if p.is_symlink() or (p.is_file() and p.stat().st_nlink>1):raise ValueError('linked submission is forbidden')
        if not p.is_file():continue
        if p.suffix not in ('.js','.cjs','.json','.txt'):raise ValueError('bundle supports JS, JSON and text files')
        raw=p.read_bytes();total+=len(raw)
        if total>2*1024**2:raise ValueError('submission exceeds 2 MiB')
        relative=p.relative_to(source) if source.is_dir() else Path('player.cjs')
        target=dest/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        hashes[str(relative)]=digest(raw)
    if not (dest/'player.cjs').is_file():raise ValueError('submission requires player.cjs')
    return hashes


def policy_profile(bundle, scratch):
    q=lambda p: json.dumps(str(Path(p).resolve()))
    allowed=[Path('/System'),Path('/usr/lib'),Path('/Library/Apple'),Path(sys.base_prefix),NODE.parent.parent,
        GAME/'dist',GAME/'node_modules',bundle,scratch]
    literals=[ROOT/'showdownbench/policy_worker.cjs',ROOT/'showdownbench/policy_launcher.py',GAME/'package.json']
    return '''(version 1)
(deny default)
(allow process-exec)
(allow signal (target self))
(allow file-read-metadata)
(allow file-read* '''+' '.join(f'(subpath {q(p)})' for p in allowed)+' '+ ' '.join(f'(literal {q(p)})' for p in literals)+'''
 (literal "/") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))
(allow file-write* (subpath '''+q(scratch)+''') (literal "/dev/null"))
(deny file-link)
(allow sysctl-read)
(allow mach-lookup (global-name "com.apple.system.logger"))
'''


def worker_spec(bundle, work, isolated=True):
    work.mkdir(parents=True,exist_ok=True)
    command=[str(NODE),'--max-old-space-size=256',str(ROOT/'showdownbench/policy_worker.cjs'),str(bundle/'player.cjs')]
    if isolated:
        if sys.platform!='darwin':raise RuntimeError('official evaluator requires macOS Seatbelt')
        profile=work.parent/(work.name+'.sb');profile.write_text(policy_profile(bundle,work))
        command=['/usr/bin/sandbox-exec','-f',str(profile),str(Path(sys.executable).resolve()),
                 '-I','-B',str(ROOT/'showdownbench/policy_launcher.py'),str(NODE),
                 str(ROOT/'showdownbench/policy_worker.cjs'),str(bundle/'player.cjs')]
    return {'command':command,'cwd':str(work)}


def aggregate(records):
    # Team ownership and player positions are swapped: four games per seed block.
    grouped={}
    for r in records:grouped.setdefault(r['block'],[]).append(r['score'])
    means=[sum(v)/len(v) for v in grouped.values()]
    rng=random.Random(1729)
    samples=sorted(sum(rng.choices(means,k=len(means)))/len(means) for _ in range(2000))
    opponents={}
    for opponent in sorted({r['opponent'] for r in records}):
        rows=[r for r in records if r['opponent']==opponent]
        opponents[opponent]={'games':len(rows),'score':sum(r['score'] for r in rows)/len(rows)}
    failures=[r for r in records if r['errors']]
    return {'games':len(records),'blocks':len(means),'score':sum(r['score'] for r in records)/len(records),
        'score_ci95':[samples[49],samples[1949]],'by_opponent':opponents,
        'wins':sum(r['winner']==r['candidate_side'] for r in records),
        'draws':sum(r['winner'] is None and r['termination']=='completed' for r in records),
        'failures':len(failures),'turn_limits':sum(r['termination']=='turn_limit' for r in records),
        'mean_turns':sum(r['turns'] for r in records)/len(records)}


def evaluate(source, out, scenarios=None, isolated=True, timeout=300, concurrency=2, replays=True, expanded=False):
    start=time.monotonic();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    hashes=freeze_bundle(Path(source),out/'candidate')
    scenarios=scenarios or make_suite()
    save(out/'scenarios.json',scenarios)
    bundles={'candidate':out/'candidate'}
    for opponent in sorted({s['opponent'] for s in scenarios}):
        folder=out/'opponents'/opponent
        if expanded:
            freeze_bundle(ROOT/'expanded/opponents'/opponent,folder)
            bundles[opponent]=folder
            continue
        folder.mkdir(parents=True)
        shutil.copyfile(POLICIES/(opponent+'.cjs'),folder/'player.cjs')
        shutil.copyfile(POLICIES/'common.cjs',folder/'common.cjs')
        bundles[opponent]=folder
    workers={}
    for scenario in scenarios:
        candidate=worker_spec(bundles['candidate'],out/'scratch'/scenario['id']/'candidate',isolated)
        opponent=worker_spec(bundles[scenario['opponent']],out/'scratch'/scenario['id']/'opponent',isolated)
        workers[scenario['id']]={'p1':candidate,'p2':opponent} if scenario['candidate_side']=='p1' else {'p1':opponent,'p2':candidate}
    games=out/'games';games.mkdir()
    save(out/'batch.json',{'scenarios':scenarios,'out':str(games),'policies':{},'workers':workers,'concurrency':concurrency,'local':not isolated})
    before=os.times()
    with (out/'engine.stdout').open('w') as stdout,(out/'engine.stderr').open('w') as stderr:
        p=subprocess.Popen([str(NODE),str(ROOT/'showdownbench/runner.cjs'),'batch',str(out/'batch.json')],
            env={'PATH':'/usr/bin:/bin','LANG':'en_US.UTF-8'},stdout=stdout,stderr=stderr,start_new_session=isolated)
        try:p.wait(timeout=timeout)
        finally:
            import signal
            try:
                if isolated:os.killpg(p.pid,signal.SIGKILL)
                elif p.poll() is None:p.kill()
            except ProcessLookupError:pass
            p.wait()
    if p.returncode:raise RuntimeError('battle runner failed: '+(out/'engine.stderr').read_text()[-2000:])
    records=[json.loads(p.read_text()) for p in sorted(games.glob('game-*.json'))]
    if len(records)!=len(scenarios):raise RuntimeError('incomplete batch; never drop missing games')
    for r in records:
        foe='p2' if r['candidate_side']=='p1' else 'p1'
        if foe in r['errors']:raise RuntimeError('trusted opponent failed: '+str(r['errors'][foe]))
    result=aggregate(records)
    after=os.times()
    result.update(candidate_hashes=hashes,isolated=isolated,wall_seconds=time.monotonic()-start,
        cpu_seconds=after.children_user+after.children_system-before.children_user-before.children_system,
        scenarios_sha256=digest((out/'scenarios.json').read_bytes()),
        records_sha256={p.name:digest(p.read_bytes()) for p in sorted(games.glob('game-*.json'))})
    result['games_per_second']=len(records)/result['wall_seconds']
    if isolated:result['provenance']=fingerprints()
    save(out/'result.json',result)
    if replays:
        from .report import render
        render(out,records,result)
    return result


def verify(out):
    out=Path(out).resolve();result=json.loads((out/'result.json').read_text())
    if 'provenance' in result and result['provenance']!=fingerprints():raise ValueError('evaluator provenance changed')
    if digest((out/'scenarios.json').read_bytes())!=result['scenarios_sha256']:raise ValueError('scenario manifest changed')
    scenarios=json.loads((out/'scenarios.json').read_text())
    if set(result['records_sha256'])!={s['id']+'.json' for s in scenarios}:
        raise ValueError('missing or extra battle records')
    for scenario in scenarios:
        record=json.loads((out/'games'/(scenario['id']+'.json')).read_text())
        if any(record[k]!=scenario[k] for k in ('id','block','opponent','candidate_side','team_ids','engine_commit')) or record['config']!={k:scenario[k] for k in ('formatid','seed','team1','team2')}:
            raise ValueError('battle record differs from its registered case')
    for name,sha in result['candidate_hashes'].items():
        if digest((out/'candidate'/name).read_bytes())!=sha:raise ValueError('candidate changed')
    for name,sha in result['records_sha256'].items():
        if digest((out/'games'/name).read_bytes())!=sha:raise ValueError('record tampered')
    records=[json.loads((out/'games'/n).read_text()) for n in result['records_sha256']]
    if any(result[k]!=v for k,v in aggregate(records).items()):raise ValueError('score changed')
    manifest=out/'verify-input.json';save(manifest,{'files':[str(out/'games'/n) for n in result['records_sha256']]})
    raw=subprocess.check_output([str(NODE),str(ROOT/'showdownbench/runner.cjs'),'verify',str(manifest)],text=True,timeout=max(120,len(records)*2))
    response=json.loads(raw);save(out/'verification.json',response);return response
