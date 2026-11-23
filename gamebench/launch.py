"""Native command adapter. No per-call, per-turn or generation overrides."""
import os, signal, subprocess, sys, time
from pathlib import Path
from .common import ROOT, read, save, load_immutable, file_hashes
from . import cohort

def credential_environment(names):
    """Only forward names explicitly declared by this system, for any provider."""
    values={};path=ROOT/'.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key,value=line.split('=',1);key=key.strip().removeprefix('export ').strip()
                if key in names:values[key]=value.strip().strip('\"\'')
    values.update({k:os.environ[k] for k in names if os.environ.get(k)})
    return {k:values[k] for k in names if values.get(k)}

def launch(root,system,task_id,repeat=0):
    m=cohort.manifest(root);p=cohort.run_path(root,system,task_id,repeat);spec=m['systems'][system]
    if (p/'execution.json').exists() or (p/'frozen.json').exists():raise ValueError('run already started or frozen')
    prepared=load_immutable(p/'prepared.json');work=p/'work'
    if file_hashes(work)!=prepared['public_files']:raise ValueError('starting workspace changed')
    command=spec['command']
    if not command:raise ValueError('system manifest must specify its native command')
    values={'python':sys.executable,'workdir':str(work),'instruction':str(work/'instructions.md')}
    command=[part.format(**values) for part in command]
    env={k:os.environ[k] for k in ('PATH','LANG','TMPDIR','DEVELOPER_DIR','SDKROOT','HTTP_PROXY','HTTPS_PROXY','NO_PROXY') if k in os.environ}
    home=p/'agent-home';home.mkdir();env.update(HOME=str(home),PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1',
        PATH=str(work/'project/.tools/node/bin')+':'+str(ROOT/'.venv/bin')+':'+env.get('PATH','/usr/bin:/bin'),
        GAMEBENCH_SYSTEM_MODEL=spec['model'])
    env.update(credential_environment(spec.get('credential_env',[])))
    start=time.monotonic();termination='agent_finished';code=None
    save(p/'execution.json',{'termination':'running','started_unix':time.time(),'command':command})
    try:
        with (p/'agent.stdout.log').open('w') as out,(p/'agent.stderr.log').open('w') as err:
            process=subprocess.Popen(command,cwd=work,env=env,stdout=out,stderr=err,start_new_session=True)
            try:code=process.wait(timeout=m['budget']['wall_seconds'])
            except subprocess.TimeoutExpired:termination='wall_time_limit'
            finally:
                # Local process groups do not contain deliberately detached sessions.
                # The formal backend must use a VM/container/cgroup teardown.
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait()
        if code not in (None,0):termination='agent_process_error'
    except OSError as e:
        termination='launch_error';save(p/'launch-error.json',{'type':type(e).__name__,'message':str(e)})
    execution={'termination':termination,'exit_code':code,'wall_seconds':time.monotonic()-start,
               'budget_seconds':m['budget']['wall_seconds'],'command':command,
               'usage':{'model_cost_usd':None,'input_tokens':None,'output_tokens':None,'cpu_seconds':None},
               'usage_status':'unavailable unless reported by native harness; never treated as zero',
               'ranking_eligible':False,'process_cleanup':'best-effort process group; detached descendants not guaranteed'}
    save(p/'execution.json',execution);cohort.freeze_run(root,system,task_id,repeat,manual=False)
    return execution
