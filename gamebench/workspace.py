"""Public, neutral task material. Local copies are writable research tools."""
import sys, shutil, subprocess
from pathlib import Path
from .common import ROOT, save, digest, file_hashes, immutable, load_immutable
from .registry import task
from . import adapters, cohort

PUBLIC_FILES={
 'mindustry':{'mindbench':['__init__.py','core.py','engine.json','catalog.json','java','replay.html','tasks','baselines']},
 'celeste':{'tasbench':['__init__.py','core.py','rooms.py','replay.html','native'],
            'tasks':['celeste_100m.json','rooms','room_prefixes']},
 'shapez':{'shapebench_v2':['__init__.py','core.py','engine.cjs','runner.cjs','report.py','replay.html','catalog.json','build.cjs','upstream-entry.js','tasks','vendor','baselines','spec.json']},
 '2048':{'bench2048':['__init__.py','core.py','engine.cjs','rules.cjs','runner.cjs','policy_worker.cjs','policy_launcher.py','report.py','replay.html','policies','spec.json']},
 'showdown':{'showdownbench':['__init__.py','core.py','runner.cjs','observations.cjs','policy_worker.cjs','policy_launcher.py','report.py','replay.html','policies','data'],
             'showdownbench_v3':['suite.py','baseline']}}

def copy_item(src,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    if src.is_dir():shutil.copytree(src,dest,symlinks=True,ignore=shutil.ignore_patterns('__pycache__','.DS_Store'))
    else:shutil.copy2(src,dest)

def public_sources(game,project):
    upstream={'celeste':'celeste-classic','2048':'2048','shapez':'shapez','showdown':'pokemon-showdown','mindustry':'mindustry'}[game]
    for name in subprocess.check_output(['git','-C',str(ROOT/upstream),'ls-files','-z']).decode().split('\0'):
        source=ROOT/upstream/name
        if name and source.is_file() and not source.is_symlink():copy_item(source,project/upstream/name)
    for folder,names in PUBLIC_FILES[game].items():
        for name in names:copy_item(ROOT/folder/name,project/folder/name)
    # Historical budgets and selection logic are not part of the new contract.
    for p in project.glob('*/spec.json'):
        from .common import read
        spec=read(p)
        for k in ('budgets','model_profile','selection','minimum_iterations','minimum_modifications'):spec.pop(k,None)
        save(p,spec)
    if game in ('showdown','2048','shapez'):copy_item(ROOT/'.tools/node',project/'.tools/node')
    if game=='mindustry':
        from mindbench.core import JAR,JAVA_HOME
        copy_item(JAR,project/'.tools/mindustry/server-release.jar')
        copy_item(JAVA_HOME,project/'.tools/mindustry/jdk/Contents/Home')
    if game=='showdown':
        for n in ('dist','node_modules'):copy_item(ROOT/'pokemon-showdown'/n,project/'pokemon-showdown'/n)

def prepare(root,system,task_id,repeat=0):
    m=cohort.manifest(root);p=cohort.run_path(root,system,task_id,repeat);t=task(task_id)
    if p.exists():raise ValueError('workspace already exists')
    w=p/'work';w.mkdir(parents=True);(w/'scratch').mkdir();(w/'feedback').mkdir()
    adapters.baseline(task_id,w/'submission');public_sources(t['game'],w/'project')
    if task_id=='showdown-expanded':
        for folder in ('expanded','tasklab'):
            copy_item(ROOT/folder,w/'project'/folder)
    dev=load_immutable(Path(root)/'development.json')[f'{task_id}/{repeat}']
    save(w/'task.json',t);save(w/'budget.json',m['budget']);save(w/'development.json',dev)
    instruction=instruction_text(t,m['budget'])
    (w/'instructions.md').write_text(instruction)
    # A development-only client: authoritative judge remains outside project/.
    # The visible host path is not represented as a security boundary.
    client='''import subprocess,sys
from pathlib import Path
work=Path(__file__).resolve().parent
cmd=[PYTHON,'-m','gamebench','dev',str(work),'--out',str(work/'feedback'/sys.argv[1])]
if len(sys.argv)>2:
    cmd+=['--validation'] if sys.argv[2]=='validation' else ['--round',sys.argv[2]]
raise SystemExit(subprocess.call(cmd,cwd=ROOT))
'''.replace('PYTHON',repr(sys.executable)).replace('ROOT',repr(str(ROOT)))
    (w/'bench.py').write_text(client)
    record={'task_id':task_id,'system':system,'repeat':repeat,'cohort_sha256':digest(m),
            'public_files':file_hashes(w),'development_sha256':digest(dev),'instruction_sha256':digest(instruction.encode())}
    immutable(p/'prepared.json',record);return {'workdir':str(w),'task_id':task_id,'ranking_eligible':False}

def instruction_text(t,b):
    details={
      'mindustry':'Submit blueprint.json with version=1 and a buildings array. See project/mindbench/tasks/'+t['instance']+'.json for the map, item, ticks, allowed blocks and build budget. Score is the target item count in the core after the final tick. The catalog and simulator are in project/mindbench. Invalid layouts score zero.',
      'celeste':'Submit script.json: {"version":1,"segments":[{"frames":N,"buttons":[...]}]}. Buttons: left, right, up, down, jump, dash. At most 600 frames at 30 Hz. Seed, initial state and bootstrap are fixed. The score is completion frames; an unsuccessful run receives 601. Source: project/celeste-classic; simulator: project/tasbench/core.py and rooms.py; task definitions: project/tasks.',
      'shapez':'Submit blueprint.json: {"version":1,"buildings":[...]}. Building fields: type, x, y and optional rotation, variant, rotationVariant. No extra fields or initial inventory. The selected map, ports, building limits and costs are in project/shapebench_v2/tasks/'+t['instance']+'.json. Catalog: project/shapebench_v2/catalog.json. Empty initial inventories; exactly 3600 ticks at 60 Hz; one point per correct delivery. Invalid layouts score zero. Array order does not alter canonical entity order. Local simulation API: project/shapebench_v2/engine.cjs. The other two maps in the engine are not scored in this task.',
      '2048':'Submit player.cjs and optional JS/JSON/text dependencies (max 128 paths, 2 MiB). Preserve the policy API shown by the baseline and project/bench2048/policy_worker.cjs. The score is the mean game score; failed policies score zero. Runtime: max 2000 moves, 4 CPU seconds/game, 100 ms/action, 2 s startup, 10 s cumulative action time, 512 MiB memory. Final policy runs in Node; research language is unrestricted. The policy receives observable game state, never the future spawn stream.',
      'showdown':'Submit player.cjs and optional JS/JSON/text dependencies (max 128 paths, 2 MiB). Preserve the API in the baseline and project/showdownbench/policy_worker.cjs. Use observable battle information only; no private opponent or RNG state. The score is win=1/draw=0.5/loss or policy failure=0 averaged over matches against the three published opponents, with both team assignments and sides. Runtime limits and action schema are defined in the published policy_worker.cjs and runner.cjs. Final policy runs in Node; research language is unrestricted.'
    }[t['game']]
    if t['id']=='showdown-expanded':
        details=details.replace('three published opponents','five published opponents across six equally weighted strata')
        details+=' Distribution, set bank, training and validation rosters and opponent programs are in project/expanded/.'
    return f'''Task: {t['id']}.
Optimize {t['metric']} ({t['direction']}) under the published rules. The original baseline is in submission/.
{details}

You may inspect and modify the public project, write programs, compile, experiment, and use your native agent tools and subagents. Analysis, implementation and iteration are your decisions. Do not access host experiments, credentials, private tests or the authoritative judge outside this workspace. Changes to local simulation code do not change scoring rules. Keep the final deliverable in submission/; other research files belong elsewhere. Links are not accepted in a submission.

Run `python3 bench.py trial-name [round|validation]` from this workspace for a development evaluation and replay. Choose a new trial-name each time. It freezes the current submission and uses the unchanged judge. Round is a nonnegative integer; it selects reproducible public random streams and (Showdown) teams from the training pool. Default round 0 uses development.json. `validation` selects the fixed public validation cases, disjoint from the training pool; repeated feedback can overfit them, so only the final test measures generalization. You may also call local simulation APIs directly. There is no separate call-count budget.

The total research budget is {b['wall_seconds']} wall-clock seconds, shared by all native subprocesses and subagents, including analysis, compilation, tool use and development evaluations. No benchmark override of model output length, tool set or context management. On process completion or deadline the last on-disk submission is frozen automatically, without selecting the best prior result. Preparation and final independent evaluation are outside the research clock. You may finish early; this is recorded as early completion.

Randomness: {t['randomness']}. Scope: {t['scope']}.
For stochastic games, final tests are generated only after every registered system/repeat has finished. All systems face the same tests for the same task/repeat. No final-test feedback is provided during research.
This is the LOCAL DEVELOPMENT backend. Target resources are {b['cpu_cores']} CPU cores, {b['memory_mib']} MiB RAM and {b['disk_mib']} MiB workspace, but this backend does not enforce them or isolate host reads. Results are unranked. The system's native behavior is preserved.
'''

def dev_evaluate(work,out,round_id=0,validation=False):
    from .common import read
    if round_id<0:raise ValueError('round must be nonnegative')
    work=Path(work).resolve();prepared=load_immutable(work.parent/'prepared.json')
    task_id=prepared['task_id'];t=task(task_id);d=read(work/'development.json');cases=d['cases']
    if digest(d)!=prepared['development_sha256']:raise ValueError('public development specification changed')
    if validation:cases=d['validation_cases']
    elif round_id:
        salt=f"gamebench-dev/{task_id}/{prepared['repeat']}/{round_id}"
        if t['game']=='2048':
            from bench2048.core import scenarios
            cases=scenarios(len(cases),salt=salt)
        elif task_id=='showdown-expanded':
            from . import expanded
            cases=expanded.cases(read(expanded.DATA/'train.json'),salt,1)
        elif t['game']=='showdown':
            from showdownbench_v3.suite import make_suite
            cases=make_suite(d['teams'],len(cases)//12,salt=salt)
    return cohort.judge_subprocess(task_id,work/'submission',out,cases)
