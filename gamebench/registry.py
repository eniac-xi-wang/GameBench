from .common import ROOT,read,digest,file_hashes

def tasks():
    result=[]
    for room in (100,300,400,600,700):
        legacy=f'celeste-classic-{room}m-'+('v1' if room==100 else 'v2')
        result.append(dict(id=f'celeste-{room}m',game='celeste',instance=legacy,
            artifact='script.json',baseline='examples/celeste_100m_baseline.json' if room==100 else f'examples/rooms/{room}m_baseline.json',
            metric='completion_frames',direction='min',failure_score=601,randomness='fixed engine seed, state, prefix and 30 Hz ticks',
            scope='fixed-instance TAS optimization; no generalization claim',submission_language='JSON button sequence, arbitrary research language'))
    for name,instance in (('cut','cut_rotate'),('paint','paint'),('stack','stack')):
        result.append(dict(id='shapez-'+name,game='shapez',instance=instance,artifact='blueprint.json',baseline=f'shapebench_v2/baselines/{instance}.json',
            metric='correct_deliveries_60s',direction='max',failure_score=0,randomness='deterministic empty state, canonical order and 60 Hz ticks',
            scope='fixed-instance factory optimization; no generalization claim',submission_language='JSON blueprint, arbitrary research language'))
    result += [dict(id='2048-policy',game='2048',instance='2048',artifact='player.cjs',baseline='bench2048/policies/greedy',
        metric='mean_game_score',direction='max',failure_score=0,randomness='public development streams; paired private test streams after all artifacts freeze',
        scope='unseen random streams under fixed game and runtime rules',submission_language='JS/JSON policy bundle; native final executables are not accepted in v0.1'),
        dict(id='showdown-policy',game='showdown',instance='gen9ou',artifact='player.cjs',baseline='showdownbench_v3/baseline',
        metric='battle_score_rate',direction='max',failure_score=0,randomness='public training team pool; disjoint held-out combinations and seeds; paired team/side blocks',
        scope='24 public configurations and 3 fixed opponents; no ladder or unknown-moveset claim',submission_language='JS/JSON policy bundle; native final executables are not accepted in v0.1')]
    result.append({**result[-1], 'id':'showdown-expanded', 'instance':'six-strata',
        'baseline':'expanded/opponents/heuristic', 'scope':'one policy across six strata and five published opponents',
        'randomness':'public training rosters; fresh legal disjoint team combinations and battle seeds after freeze'})
    for name in ('plastanium-bio-oil','blast-compound','surge-alloy'):
        result.append(dict(id='mindustry-'+name, game='mindustry', instance=name,
            artifact='blueprint.json', baseline=f'mindbench/baselines/{name}.json', metric='target_items_in_core',
            direction='max', failure_score=0, randomness='fixed map and ticks; canonical initial adjacency order',
            scope='fixed complex-production map', submission_language='JSON blueprint, arbitrary research language'))
    return result

def task(task_id):
    found=[t for t in tasks() if t['id']==task_id]
    if not found:raise ValueError('unknown task: '+task_id)
    return found[0]

def fingerprint(task_id):
    t=task(task_id)
    if t['game']=='celeste':
        from tasbench import core,rooms
        source=core.source_hashes() if t['instance']==rooms.LEGACY_ID else rooms.source_hashes(t['instance'])
    elif t['game']=='shapez':
        from shapebench_v2 import core
        source=core.fingerprints()
    elif t['game']=='2048':
        from bench2048 import core
        source=core.fingerprints()
    elif t['game']=='showdown':
        from showdownbench_v3 import suite
        source=suite.fingerprints()
    if t['game']=='mindustry':
        from mindbench import core
        source=core.fingerprints()
    if task_id=='showdown-expanded':
        source.update({'expanded/'+k:v for k,v in file_hashes(ROOT/'expanded').items()})
        source.update({'tasklab/'+k:v for k,v in file_hashes(ROOT/'tasklab').items()})
    baseline=file_hashes(ROOT/t['baseline'])
    return {'task':t,'source_sha256':digest(source),'baseline_sha256':digest(baseline),
        'sources':source,'baseline_files':baseline,'release':'gamebench-local-v0.2'}

def budget(name):
    values=read(ROOT/'benchmarks/budgets.json')
    if name not in values:raise ValueError('unknown budget profile')
    return {**values[name],'id':name,'model_requests_cap':None,'tool_calls_cap':None,'output_tokens_override':None,
        'evaluation_calls_cap':None,'native_subagents_share_budget':True}
