"""One command prepares dependencies, runs all systems, seals, grades and verifies."""
import argparse
from datetime import datetime, timezone
import importlib.util
from pathlib import Path

from .common import ROOT, read, save
from . import adapters, cohort, workspace
from .launch import credential_environment, launch
from .registry import tasks
from .setup import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='list task IDs without downloading anything')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--tasks', nargs='+', metavar='ID')
    selection.add_argument('--all', action='store_true', help='run every registered task')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--submission', type=Path, help='grade an existing submission directory for one task')
    source.add_argument('--system', action='append', metavar='NAME_OR_JSON',
                        help='repeat to compare native systems on the same final cases')
    parser.add_argument('--budget', choices=('smoke','30m','2h','8h'), default='smoke')
    parser.add_argument('--out', type=Path, help='new output directory (default: timestamped runs directory)')
    args = parser.parse_args()
    catalog = {t['id']:t for t in tasks()}
    if args.list:
        for name, t in catalog.items():
            print(f"{name:32s} {t['metric']} ({t['direction']})")
        return 0
    chosen = list(catalog) if args.all else args.tasks or ['celeste-100m']
    if len(set(chosen)) != len(chosen) or set(chosen)-catalog.keys():
        parser.error('Use distinct task IDs from --list')
    supplied = args.submission
    if supplied is not None and (len(chosen) != 1 or not supplied.is_dir() or supplied.is_symlink()):
        parser.error('--submission requires one task and a real submission directory')
    systems = []
    for name in args.system or (['saved-submission'] if supplied else ['baseline-replay']):
        path = Path(name)
        if not path.is_file():
            path = ROOT/'benchmarks/systems'/(name+'.json')
        spec = read(path)
        if not supplied and not spec.get('command') and spec != read(ROOT/'benchmarks/systems/baseline-replay.json'):
            parser.error(f'{name} has no native command')
        if spec['harness'] == 'deepseek-harness-sdk':
            if importlib.util.find_spec('deepseek_harness') is None:
                parser.error('Install requirements-agent.txt in the Python environment running bench')
            if not credential_environment(['DEEPSEEK_API_KEY']):
                parser.error('Set DEEPSEEK_API_KEY in the environment or repository .env')
        systems.append(path)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = (args.out or ROOT/'runs'/stamp).resolve()
    if out.exists():
        parser.error(f'Output already exists: {out}')
    prepare({catalog[t]['game'] for t in chosen})
    manifest = cohort.create(out, chosen, systems, args.budget)
    print(f'Run directory: {out}', flush=True)
    failed = False
    for system, task, repeat in cohort.members(manifest):
        print(f'{system} / {task} / repeat {repeat+1}', flush=True)
        work = Path(workspace.prepare(out, system, task, repeat)['workdir'])
        if supplied:
            adapters.freeze(task, supplied, work/'incoming')
            (work/'submission').rename(work.parent/'starting-baseline')
            (work/'incoming').rename(work/'submission')
        if manifest['systems'][system]['command']:
            result = launch(out, system, task, repeat)
            failed |= result['termination'] in ('launch_error','agent_process_error')
        else:
            cohort.freeze_run(out, system, task, repeat)
    print('All submissions frozen. Generating final cases and verifying replays.', flush=True)
    cohort.seal(out)
    report = cohort.grade(out)
    summary = cohort.compare(out)
    save(out/'comparison.json', summary)
    for row in report['rows']:
        print(f"{row['system']:25s} {row['task_id']:32s} {row['baseline']} -> {row['score']}  {row['execution']['termination']}")
        if not row['valid_artifact'] or not row['replay'] or not (out/row['replay']).is_file():
            failed = True
        if row['system'] == 'baseline-replay':
            # CPU deadlines can introduce failures even with identical sources.
            failed |= row['score'] != row['baseline'] or bool(row['details'].get('failures'))
    print(f"Report: {out/'index.html'}")
    return int(failed)
