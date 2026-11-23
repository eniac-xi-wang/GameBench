"""Pre-register runs; generate paired tests only after every submission is frozen.

Hashes detect accidental changes. They are not an access-control mechanism; this
local backend is deliberately excluded from official rankings.
"""
import os, platform, shutil, subprocess, sys, time
from pathlib import Path
from .common import ROOT, read, save, digest, file_hashes, immutable, load_immutable, safe_id
from .registry import task, fingerprint, budget
from . import adapters

def integration_hashes():
    return file_hashes(ROOT/'gamebench') | {'suite':digest(read(ROOT/'benchmarks/suite.json')),
                                          'budgets':digest(read(ROOT/'benchmarks/budgets.json'))}

def environment(task_ids=None):
    node=ROOT/'.tools/node/bin/node'
    return {'backend':'local-development','os':platform.platform(),'architecture':platform.machine(),
            'python':sys.version,'node':subprocess.check_output([str(node),'--version'],text=True).strip() if node.exists() and (task_ids is None or any(task(t)['game'] in ('showdown','2048','shapez') for t in task_ids)) else None,
            'resource_limits_enforced':False,'agent_read_isolation':False,
            'network':'native host access; no benchmark filtering','ranking_eligible':False}

def create(root, task_ids, systems, profile='smoke'):
    root=Path(root).resolve()
    if root.exists():raise ValueError('cohort directory already exists')
    task_ids=list(task_ids)
    if not task_ids or len(set(task_ids))!=len(task_ids):raise ValueError('select unique tasks')
    specs=[read(p) for p in systems];ids=[safe_id(s['id']) for s in specs]
    if not ids or len(set(ids))!=len(ids):raise ValueError('select unique agent systems')
    for s in specs:
        for k in ('harness','harness_version','model','command'):
            if k not in s:raise ValueError('system manifest missing '+k)
    b=budget(profile);root.mkdir(parents=True)
    manifest={'version':1,'release':'gamebench-local-v0.2','tasks':{i:fingerprint(i) for i in task_ids},
              'systems':{s['id']:s for s in specs},'budget':b,'environment':environment(task_ids),
              'integration':integration_hashes(),'selection':'last on-disk submission at run termination',
              'replicates':b['repeats'],'created_unix':time.time()}
    public={}
    for i in task_ids:
        for repeat in range(b['repeats']):
            public[f'{i}/{repeat}']=development_data(i,repeat,profile)
    immutable(root/'development.json',public)
    manifest['development_sha256']=digest(public)
    immutable(root/'cohort.json',manifest)
    return manifest

def development_data(task_id,repeat,profile):
    t=task(task_id);salt=f'gamebench-local-v0.2/{task_id}/{repeat}'
    if task_id=='showdown-expanded':
        from . import expanded
        return expanded.development(salt)
    if t['game']=='2048':
        from bench2048.core import scenarios
        return {'cases':scenarios(2 if profile=='smoke' else 16,salt=salt),
                'validation_cases':scenarios(2 if profile=='smoke' else 32,salt=salt+'/validation')}
    if t['game']=='showdown':
        from showdownbench_v3 import suite
        teams=suite.draw_teams(256,salt=salt)
        vp=1 if profile=='smoke' else 32
        validation=suite.draw_teams(2*vp,excluded=[suite.team_key(x['team']) for x in teams],salt=salt+'/validation')
        return {'teams':teams,'cases':suite.make_suite(teams,1 if profile=='smoke' else 16,salt=salt),
                'validation_teams':validation,'validation_cases':suite.make_suite(validation,vp,salt=salt+'/validation')}
    return {'cases':None,'validation_cases':None}

def manifest(root):
    m=load_immutable(Path(root)/'cohort.json')
    if m['integration']!=integration_hashes():raise ValueError('integration changed; create a new cohort')
    if m['environment']!=environment(m['tasks']):raise ValueError('runtime environment changed; create a new cohort')
    for i,fp in m['tasks'].items():
        if fp!=fingerprint(i):raise ValueError('task, baseline or judge changed: '+i)
    if digest(load_immutable(Path(root)/'development.json'))!=m['development_sha256']:raise ValueError('development data changed')
    return m

def members(m):
    return [(s,t,r) for s in m['systems'] for t in m['tasks'] for r in range(m['replicates'])]

def run_path(root,system,task_id,repeat):
    m=manifest(root)
    if (system,task_id,repeat) not in members(m):raise ValueError('run was not pre-registered')
    return Path(root).resolve()/'runs'/system/task_id/str(repeat)

def freeze_run(root,system,task_id,repeat,manual=True):
    p=run_path(root,system,task_id,repeat)
    if not (p/'prepared.json').exists():raise ValueError('prepare the workspace first')
    if (p/'frozen.json').exists():raise ValueError('run already frozen; cannot replace a tested submission')
    if manual and (p/'execution.json').exists():raise ValueError('managed execution owns submission freezing')
    status='submitted';error=None;hashes={}
    try:hashes=adapters.freeze(task_id,p/'work/submission',p/'artifact')
    except ValueError as e:
        status='invalid_submission';error=str(e)
        if (p/'artifact').exists():shutil.rmtree(p/'artifact')
    execution=read(p/'execution.json') if (p/'execution.json').exists() else {'termination':'manual_snapshot','wall_seconds':None}
    if execution['termination'] in ('agent_process_error','launch_error'):
        status='system_error'
        error=execution['termination']
    record={'status':status,'error':error,'artifact_hashes':hashes,'frozen_unix':time.time(),
            'execution':execution,'prepared_sha256':digest(load_immutable(p/'prepared.json'))}
    immutable(p/'frozen.json',record);return record

def frozen(p):
    f=load_immutable(p/'frozen.json')
    if f['status']=='submitted' and f['artifact_hashes']!=file_hashes(p/'artifact'):raise ValueError('frozen submission changed')
    if f['prepared_sha256']!=digest(load_immutable(p/'prepared.json')):raise ValueError('prepared record changed')
    return f

def seal(root):
    root=Path(root).resolve();m=manifest(root)
    if (root/'sealed.json').exists():raise ValueError('cohort already sealed')
    submissions={}
    for s,t,r in members(m):
        p=run_path(root,s,t,r)
        if not (p/'frozen.json').exists():raise ValueError(f'all registered runs must freeze first: {s}/{t}/{r}')
        submissions[f'{s}/{t}/{r}']=digest(frozen(p))
    dev=load_immutable(root/'development.json');tests={}
    for i in m['tasks']:
        for r in range(m['replicates']):
            k=f'{i}/{r}';d=dev[k];g=task(i)['game'];data={'cases':None}
            if g=='2048':
                from bench2048.core import scenarios
                data={'cases':scenarios(2 if m['budget']['id']=='smoke' else 128,excluded=[x['key'] for x in d['cases']+d['validation_cases']])}
            elif i=='showdown-expanded':
                from . import expanded
                data=expanded.final(m['budget']['id']=='smoke')
            elif g=='showdown':
                from showdownbench_v3 import suite
                pairs=1 if m['budget']['id']=='smoke' else 96
                teams=suite.draw_teams(2*pairs,excluded=[suite.team_key(x['team']) for x in d['teams']+d['validation_teams']])
                data={'teams':teams,'cases':suite.make_suite(teams,pairs)}
            tests[k]=data
    immutable(root/'private/tests.json',tests)
    seal={'submissions':submissions,'test_sha256':digest(tests),'development_sha256':digest(dev),'sealed_unix':time.time()}
    immutable(root/'sealed.json',seal);return seal

def judge_subprocess(task_id,source,out,cases=None,isolated=True):
    out=Path(out)
    case_path=out.with_name(out.name+'-cases.json')
    if cases is not None:save(case_path,cases)
    cmd=[sys.executable,'-m','gamebench','_judge',task_id,str(source),str(out)]
    if cases is not None:cmd+=['--cases',str(case_path)]
    if not isolated:cmd+=['--no-policy-isolation']
    env={'PATH':str(ROOT/'.tools/node/bin')+':/usr/bin:/bin:/usr/sbin:/sbin',
         'PYTHONPATH':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1','LANG':'en_US.UTF-8'}
    env.update({key:os.environ[key] for key in ('TMPDIR','SDKROOT','DEVELOPER_DIR') if key in os.environ})
    if task(task_id)['game']=='mindustry':
        from mindbench.core import JAVA_HOME, RUNTIME
        env.update(MINDBENCH_JAVA_HOME=str(JAVA_HOME),MINDBENCH_RUNTIME=str(RUNTIME))
    result=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=7200)
    if result.returncode:
        if out.exists():
            out.rename(out.with_name(out.name+f'.failed-{time.time_ns()}'))
        raise RuntimeError('independent judge failed: '+result.stderr[-3000:])
    return read(out/'result.json')

def grade(root,isolated=True):
    root=Path(root).resolve();m=manifest(root);sealed=load_immutable(root/'sealed.json')
    tests=load_immutable(root/'private/tests.json')
    if digest(tests)!=sealed['test_sha256']:raise ValueError('test set changed')
    rows=[]
    for s,t,r in members(m):
        p=run_path(root,s,t,r);f=frozen(p);k=f'{s}/{t}/{r}'
        if digest(f)!=sealed['submissions'][k]:raise ValueError('submission was changed after cohort sealing')
        cases=tests[f'{t}/{r}']['cases'];base=root/'grading/baselines'/t/str(r)
        if not base.exists():
            src=base.with_name(base.name+'-source');adapters.baseline(t,src)
            judge_subprocess(t,src,base,cases,isolated)
        adapters.verify(base)
        if read(base/'result.json')['cases_sha256']!=(digest(cases) if cases is not None else None):raise ValueError('baseline test set mismatch')
        target=root/'grading/systems'/s/t/str(r)
        if f['status']=='submitted':
            if not target.exists():judge_subprocess(t,p/'artifact',target,cases,isolated)
            adapters.verify(target);result=read(target/'result.json')
            if result['artifact_hashes']!=f['artifact_hashes']:raise ValueError('graded artifact differs from frozen submission')
            if result['cases_sha256']!=(digest(cases) if cases is not None else None):raise ValueError('candidate test set mismatch')
            if result['policy_isolation']!=isolated or read(base/'result.json')['policy_isolation']!=isolated:raise ValueError('cannot change judging mode within a cohort')
            pair=adapters.paired(t,base,target)
        else:
            result={'primary':task(t)['failure_score'],'valid_artifact':False,'details':{'error':f['error']},'replay':None}
            pair=None
        rows.append({'system':s,'task_id':t,'repeat':r,'status':f['status'],'score':result['primary'],
                     'valid_artifact':result['valid_artifact'],'baseline':read(base/'result.json')['primary'],
                     'paired':pair,'details':result['details'],'execution':f['execution'],
                     'result':str(target.relative_to(root)/'result.json') if f['status']=='submitted' else None,
                     'replay':str(target.relative_to(root)/result['replay']) if result['replay'] else None})
    report={'release':m['release'],'ranking_eligible':False,'label':'LOCAL DEVELOPMENT — not a controlled agent-system comparison',
            'cohort_sha256':digest(m),'sealed_sha256':digest(sealed),'rows':rows,
            'policy_isolation':isolated,'generated_unix':time.time()}
    immutable(root/'report.json',report)
    from .report import render
    render(root,report);return report

def compare(root,official=False):
    root=Path(root);m=manifest(root);report=load_immutable(root/'report.json');sealed=load_immutable(root/'sealed.json')
    if report['cohort_sha256']!=digest(m) or report['sealed_sha256']!=digest(sealed):raise ValueError('report belongs to different conditions')
    if digest(load_immutable(root/'private/tests.json'))!=sealed['test_sha256']:raise ValueError('test set changed')
    if digest(load_immutable(root/'development.json'))!=sealed['development_sha256']:raise ValueError('development data changed')
    expected=set(members(m));actual=[(x['system'],x['task_id'],x['repeat']) for x in report['rows']]
    if len(actual)!=len(expected) or set(actual)!=expected:raise ValueError('missing, duplicate or unregistered repeats')
    for s,t,r in expected:
        if digest(frozen(run_path(root,s,t,r)))!=sealed['submissions'][f'{s}/{t}/{r}']:raise ValueError('submission changed')
    for t in m['tasks']:
        for r in range(m['replicates']):
            public=[load_immutable(run_path(root,s,t,r)/'prepared.json')['public_files'] for s in m['systems']]
            if any(x!=public[0] for x in public):raise ValueError('agent systems received different initial public material')
    if official:raise ValueError('official ranking unavailable: local backend cannot enforce agent read isolation, aggregate CPU/RAM/disk limits or clean process teardown')
    summary=[]
    for s in m['systems']:
        for t in m['tasks']:
            rows=[x for x in report['rows'] if (x['system'],x['task_id'])==(s,t)]
            summary.append({'system':s,'task_id':t,'direction':task(t)['direction'],'metric':task(t)['metric'],
                            'scores':[x['score'] for x in rows],'mean':sum(x['score'] for x in rows)/len(rows),
                            'baseline_mean':sum(x['baseline'] for x in rows)/len(rows),
                            'valid_runs':sum(x['valid_artifact'] for x in rows),'repeats':len(rows)})
    return {'ranking_eligible':False,'label':report['label'],'per_task':summary,'overall_score':None}
