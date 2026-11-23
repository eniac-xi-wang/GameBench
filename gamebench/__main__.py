import argparse, json, shutil, sys
from pathlib import Path
from .common import ROOT, read
from .registry import tasks
from . import adapters, cohort, workspace

def main():
    parser=argparse.ArgumentParser(description='GameBench complete-agent-system protocol; local backend is unranked')
    sub=parser.add_subparsers(dest='op',required=True)
    sub.add_parser('list');sub.add_parser('doctor')
    p=sub.add_parser('create');p.add_argument('root');p.add_argument('--tasks',nargs='+',required=True);p.add_argument('--systems',nargs='+',required=True);p.add_argument('--budget',default='smoke',choices=['smoke','30m','2h','8h'])
    for op in ('prepare','freeze','launch'):
        p=sub.add_parser(op);p.add_argument('root');p.add_argument('system');p.add_argument('task');p.add_argument('--repeat',type=int,default=0)
    p=sub.add_parser('dev');p.add_argument('work');p.add_argument('--out',required=True);p.add_argument('--round',type=int,default=0);p.add_argument('--validation',action='store_true')
    for op in ('seal','grade','compare'):
        p=sub.add_parser(op);p.add_argument('root')
        if op=='grade':p.add_argument('--no-policy-isolation',action='store_true')
        if op=='compare':p.add_argument('--official',action='store_true')
    p=sub.add_parser('verify');p.add_argument('out')
    p=sub.add_parser('_judge');p.add_argument('task');p.add_argument('source');p.add_argument('out');p.add_argument('--cases');p.add_argument('--no-policy-isolation',action='store_true')
    a=parser.parse_args()
    if a.op=='list':result=tasks()
    elif a.op=='doctor':
        import importlib.metadata
        result={'environment':cohort.environment(),'docker':shutil.which('docker'),'harbor':shutil.which('harbor'),
                'deepseek_sdk':next((d.version for d in importlib.metadata.distributions() if (d.metadata['Name'] or '').lower()=='deepseek-harness-sdk'),None),
                'formal_backend_ready':False,'blockers':['no enforced whole-agent resource/read isolation backend','stochastic policy isolation currently requires macOS Seatbelt']}
    elif a.op=='create':result=cohort.create(a.root,a.tasks,a.systems,a.budget)
    elif a.op=='prepare':result=workspace.prepare(a.root,a.system,a.task,a.repeat)
    elif a.op=='freeze':result=cohort.freeze_run(a.root,a.system,a.task,a.repeat)
    elif a.op=='launch':
        from .launch import launch
        result=launch(a.root,a.system,a.task,a.repeat)
    elif a.op=='dev':result=workspace.dev_evaluate(a.work,a.out,a.round,a.validation)
    elif a.op=='seal':result=cohort.seal(a.root)
    elif a.op=='grade':result=cohort.grade(a.root,not a.no_policy_isolation)
    elif a.op=='compare':result=cohort.compare(a.root,a.official)
    elif a.op=='verify':result=adapters.verify(a.out)
    else:
        result=adapters.evaluate(a.task,a.source,a.out,read(a.cases) if a.cases else None,not a.no_policy_isolation)
        adapters.verify(a.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,FileNotFoundError) as e:
        print(str(e),file=sys.stderr);raise SystemExit(2)
