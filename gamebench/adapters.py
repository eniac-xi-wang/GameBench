"""One read-only integration over the frozen historical game evaluators."""
import json,shutil,tempfile,stat
from pathlib import Path
from .common import ROOT,read,save,digest,file_hashes
from .registry import task,fingerprint

def baseline(task_id,dest):
    t=task(task_id);src=ROOT/t['baseline'];dest=Path(dest);dest.mkdir(parents=True,exist_ok=False)
    if src.is_file():shutil.copy2(src,dest/t['artifact'])
    else:
        for p in src.iterdir():
            if p.is_file():shutil.copy2(p,dest/p.name)

def freeze(task_id,source,dest):
    t=task(task_id);source=Path(source);dest=Path(dest)
    if source.is_symlink() or not source.is_dir():raise ValueError('submission must be a real directory')
    for p in source.rglob('*'):
        if p.is_symlink() or (p.is_file() and p.stat().st_nlink!=1):raise ValueError('submission cannot contain links')
        if not (stat.S_ISREG(p.stat().st_mode) or stat.S_ISDIR(p.stat().st_mode)):raise ValueError('submission contains a special file')
    if t['game'] in ('celeste','shapez','mindustry'):
        if {p.name for p in source.iterdir()}!={t['artifact']}:raise ValueError('submission must contain only '+t['artifact'])
        if not (source/t['artifact']).is_file():raise ValueError('artifact must be a regular file')
        data=(source/t['artifact']).read_bytes()
        if len(data)>256*1024:raise ValueError('submission exceeds 256 KiB')
        obj=json.loads(data);json.dumps(obj,allow_nan=False)
        if t['game']=='celeste':
            from tasbench.core import parse_script
            parse_script(obj)
        dest.mkdir(parents=True,exist_ok=False);(dest/t['artifact']).write_bytes(data)
    elif t['game']=='2048':
        from bench2048.core import freeze as f
        f(source,dest)
    else:
        from showdownbench.core import freeze_bundle
        freeze_bundle(source,dest)
    return file_hashes(dest)

def evaluate(task_id,source,out,cases=None,isolated=True):
    t=task(task_id);source=Path(source).resolve();out=Path(out).resolve()
    if out.exists():raise ValueError('evaluation output already exists')
    out.mkdir(parents=True);freeze(task_id,source,out/'artifact')
    raw=out/'engine';primary=None;valid=False;replay=None
    if t['game']=='celeste':
        from tasbench import core,rooms
        obj=read(out/'artifact/script.json')
        r=core.evaluate(obj,raw) if t['instance']==rooms.LEGACY_ID else rooms.evaluate(obj,raw,t['instance'])
        valid=r['success'];primary=r['completion_frames'] if valid else t['failure_score'];replay='engine/replay.html'
        details={k:r[k] for k in ('success','completion_frames','deaths','frames') if k in r}
    elif t['game']=='mindustry':
        from mindbench import core
        r=core.evaluate(core.task_path(t['instance']),out/'artifact/blueprint.json',raw)
        primary=r['score'];valid=r['valid'];replay='engine/replay.html'
        details={k:r[k] for k in ('task_id','valid','score','build_cost')}
    elif t['game']=='shapez':
        from shapebench_v2 import core
        with tempfile.TemporaryDirectory(prefix='gamebench-shapez-') as temp:
            bundle=Path(temp)/'bundle';shutil.copytree(core.BASELINE,bundle)
            shutil.copy2(out/'artifact/blueprint.json',bundle/(t['instance']+'.json'))
            r=core.evaluate(bundle,raw)
        r=next(x for x in r['tasks'] if x['task_id']==t['instance'])
        primary=r['score'];valid=r['valid'];details=r;replay='engine/replays/'+t['instance']+'.html' if valid else 'engine/index.html'
    elif t['game']=='2048':
        from bench2048 import core
        if cases is None:raise ValueError('2048 requires explicit committed cases')
        r=core.evaluate(out/'artifact',raw,cases,isolated=isolated,concurrency=1)
        primary=r['score'];valid=True;details=core.public(r);replay='engine/index.html'
    else:
        from showdownbench import core
        from showdownbench_v3.suite import public_summary
        if cases is None:raise ValueError('Showdown requires explicit committed cases')
        r=core.evaluate(out/'artifact',raw,cases,isolated=isolated,concurrency=2,timeout=max(600, len(cases)*8), expanded=task_id=='showdown-expanded')
        primary=r['score'];valid=True;details=public_summary(r);replay='engine/index.html'
    result={'schema_version':1,'task_id':task_id,'metric':t['metric'],'direction':t['direction'],
        'primary':primary,'valid_artifact':bool(valid),'details':details,'replay':replay,
        'artifact_hashes':file_hashes(out/'artifact'),'task_fingerprint':fingerprint(task_id),
        'cases_sha256':digest(cases) if cases is not None else None,'policy_isolation':isolated}
    save(out/'result.json',result);return result

def verify(out):
    out=Path(out);r=read(out/'result.json');t=task(r['task_id'])
    if r['task_fingerprint']!=fingerprint(t['id']):raise ValueError('task/evaluator release changed')
    if r['artifact_hashes']!=file_hashes(out/'artifact'):raise ValueError('frozen artifact changed')
    raw=read(out/'engine/result.json')
    if t['game']=='celeste':
        from tasbench import core,rooms
        if core.parse_script(read(out/'artifact/script.json'))!=core.parse_script(read(out/'engine/script.json')):raise ValueError('judge ran a different script')
        check=core.verify(out/'engine') if t['instance']==rooms.LEGACY_ID else rooms.verify(out/'engine')
        expected=raw['completion_frames'] if raw['success'] else t['failure_score']
        expected_valid=raw['success'];expected_details={k:raw[k] for k in ('success','completion_frames','deaths','frames') if k in raw}
    elif t['game']=='mindustry':
        from mindbench import core
        if (out/'artifact/blueprint.json').read_bytes()!=(out/'engine/blueprint.json').read_bytes() or read(out/'engine/task.json')!=read(core.task_path(t['instance'])):
            raise ValueError('judge ran a different blueprint or map')
        check=core.verify(out/'engine');expected=raw['score'];expected_valid=raw['valid']
        expected_details={k:raw[k] for k in ('task_id','valid','score','build_cost')}
    elif t['game']=='shapez':
        from shapebench_v2 import core
        if (out/'artifact/blueprint.json').read_bytes()!=(out/'engine/candidate'/(t['instance']+'.json')).read_bytes():raise ValueError('judge ran a different blueprint')
        check=core.verify(out/'engine');expected=next(x['score'] for x in raw['tasks'] if x['task_id']==t['instance'])
        expected_details=next(x for x in raw['tasks'] if x['task_id']==t['instance']);expected_valid=expected_details['valid']
    else:
        if t['game']=='2048':from bench2048 import core
        else:from showdownbench import core
        if file_hashes(out/'engine/candidate')!=r['artifact_hashes']:raise ValueError('judge ran a different policy')
        check=core.verify(out/'engine');expected=raw['score']
        expected_valid=True
        if t['game']=='2048':expected_details=core.public(raw)
        else:
            from showdownbench_v3.suite import public_summary
            expected_details=public_summary(raw)
        if digest(read(out/'engine/scenarios.json'))!=r['cases_sha256']:raise ValueError('test cases changed')
    if r['valid_artifact']!=bool(expected_valid) or r['details']!=expected_details:raise ValueError('summary differs from original engine')
    if r['metric']!=t['metric'] or r['direction']!=t['direction']:raise ValueError('metric contract changed')
    if expected!=r['primary']:raise ValueError('reported metric differs from original engine')
    checked={'valid':True,'engine_verification':check};save(out/'verification.json',checked);return checked

def paired(task_id,baseline_out,agent_out):
    t=task(task_id)
    if t['game']=='2048':
        from bench2048 import core
        return core.paired(core.records(Path(baseline_out)/'engine'),core.records(Path(agent_out)/'engine'))
    if t['game']=='showdown':
        from showdownbench_v3 import suite
        difference = suite.paired_difference
        if task_id=='showdown-expanded':
            from .expanded import paired as difference
        return difference(suite.records(Path(baseline_out)/'engine'),suite.records(Path(agent_out)/'engine'))
    b=read(Path(baseline_out)/'result.json');r=read(Path(agent_out)/'result.json')
    gain=(b['primary']-r['primary']) if t['direction']=='min' else (r['primary']-b['primary'])
    return {'improvement':gain,'unit':t['metric'],'baseline':b['primary'],'candidate':r['primary']}
