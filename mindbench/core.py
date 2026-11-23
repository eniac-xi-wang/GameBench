"""Data-only submissions, pinned native engine, and independent replay verification."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import stat
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parent
RUNTIME = Path(os.environ.get('MINDBENCH_RUNTIME', ROOT / '.tools/mindustry')).resolve()
JAVA_HOME = Path(os.environ.get('MINDBENCH_JAVA_HOME', RUNTIME / 'jdk/Contents/Home')).resolve()
JAR = RUNTIME / 'server-release.jar'
MAX_BLUEPRINT_BYTES = 256 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def strict_json(data):
    def pairs(values):
        result = {}
        for k, v in values:
            if k in result:
                raise ValueError('duplicate JSON key: ' + k)
            result[k] = v
        return result
    value = json.loads(data, object_pairs_hook=pairs,
                       parse_constant=lambda x: (_ for _ in ()).throw(ValueError('non-finite JSON')))
    json.dumps(value, allow_nan=False)
    return value


def read(path):
    return strict_json(Path(path).read_bytes())


def manifest():
    return read(PACKAGE / 'engine.json')


def build():
    expected = manifest()['server_sha256']
    if not JAR.is_file() or digest(JAR.read_bytes()) != expected:
        raise RuntimeError('Missing or modified pinned engine; run python -m mindbench.bootstrap')
    source = PACKAGE / 'java/FactoryRunner.java'
    key = digest(source.read_bytes() + expected.encode())[:24]
    dest = RUNTIME / 'build' / key
    if not (dest / 'FactoryRunner.class').exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent) as temp:
            subprocess.run([str(JAVA_HOME / 'bin/javac'), '--release', '17', '-cp', str(JAR),
                            '-d', temp, str(source)], check=True, capture_output=True, timeout=60)
            try:
                Path(temp).rename(dest)
            except FileExistsError:
                pass
    return dest


def fingerprints():
    classes = build()
    files = sorted(PACKAGE.glob('*.py')) + sorted(PACKAGE.glob('*.json'))
    files += sorted(PACKAGE.glob('*.html')) + sorted((PACKAGE / 'java').glob('*.java'))
    files += sorted((PACKAGE / 'tasks').glob('*.json'))
    result = {str(p.relative_to(PACKAGE)): digest(p.read_bytes()) for p in files}
    result['engine/server-release.jar'] = digest(JAR.read_bytes())
    result['runtime/java'] = digest((JAVA_HOME / 'bin/java').read_bytes())
    result['runtime/release'] = digest((JAVA_HOME / 'release').read_bytes())
    for p in sorted(classes.glob('*.class')):
        result['compiled/' + p.name] = digest(p.read_bytes())
    return result


def run(payload, timeout=30):
    classes = build()
    with tempfile.TemporaryDirectory(prefix='mindbench-') as folder:
        work = Path(folder); save(work / 'request.json', payload)
        def limits():
            resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
            resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024**2, 32 * 1024**2))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        p = subprocess.run([str(JAVA_HOME / 'bin/java'), '-Xmx512m', '-XX:ActiveProcessorCount=1',
                            '-cp', str(JAR) + os.pathsep + str(classes), 'FactoryRunner',
                            str(work / 'request.json'), str(work / 'record.json'), str(work / 'data')],
                           cwd=work, env={'PATH': '/usr/bin:/bin', 'HOME': str(work), 'TMPDIR': str(work),
                                          'LANG': 'en_US.UTF-8'},
                           capture_output=True, text=True, timeout=timeout, preexec_fn=limits)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        if p.returncode:
            raise RuntimeError('native engine failed: ' + p.stderr[-3000:])
        return read(work / 'record.json'), {'wall_seconds': time.monotonic() - start,
            'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime}


def integer(x):
    return type(x) is int


def validate(blueprint):
    if not isinstance(blueprint, dict) or set(blueprint) != {'version', 'buildings'} or type(blueprint['version']) is not int or blueprint['version'] != 1:
        raise ValueError('expected exactly version=1 and buildings')
    rows = blueprint['buildings']
    if not isinstance(rows, list) or len(rows) > 512:
        raise ValueError('expected at most 512 buildings')
    for p in rows:
        if not isinstance(p, dict) or set(p) - {'block', 'x', 'y', 'rotation', 'links', 'item'}:
            raise ValueError('unsupported building fields')
        if not isinstance(p.get('block'), str) or not all(integer(p.get(k)) for k in ('x', 'y')):
            raise ValueError('block name and integer coordinates required')
        if not all(0 <= p[k] < 128 for k in ('x', 'y')):
            raise ValueError('coordinate out of range')
        if not integer(p.get('rotation', 0)) or not 0 <= p.get('rotation', 0) <= 3:
            raise ValueError('rotation must be an integer in 0..3')
        if 'item' in p and not isinstance(p['item'], str):
            raise ValueError('item must be a string')
        if 'links' in p:
            links = p['links']
            if not isinstance(links, list) or len(links) > 20:
                raise ValueError('at most 20 power links')
            if any(not isinstance(v, list) or len(v) != 2 or not all(integer(x) and 0 <= x < 128 for x in v) for v in links):
                raise ValueError('power links must be absolute integer coordinate pairs')
            if len({tuple(v) for v in links}) != len(links):
                raise ValueError('duplicate power links')
    return blueprint


def simulate_bytes(task, data):
    try:
        if len(data) > MAX_BLUEPRINT_BYTES:
            raise ValueError('blueprint exceeds 256 KiB')
        candidate = validate(strict_json(data))
    except (ValueError, TypeError, UnicodeError) as e:
        return {'valid': False, 'score': 0, 'error': str(e)}, {'wall_seconds': 0, 'cpu_seconds': 0}
    return run({'task': task, 'blueprint': candidate})


def read_candidate(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('candidate must be a regular unlinked file')
        data = f.read(MAX_BLUEPRINT_BYTES + 1)
        if len(data) > MAX_BLUEPRINT_BYTES:
            raise ValueError('blueprint exceeds 256 KiB')
    return data


def evaluate(task_file, candidate_file, out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('output already exists')
    task = read(task_file); data = read_candidate(candidate_file)
    source = fingerprints()
    out.mkdir(parents=True)
    save(out / 'task.json', task); (out / 'blueprint.json').write_bytes(data)
    record, timing = simulate_bytes(task, data)
    if fingerprints() != source:
        raise RuntimeError('evaluator changed during evaluation')
    save(out / 'record.json', record)
    result = {'protocol': manifest()['evaluation_protocol'], 'task_id': task['id'], 'family': task['family'],
              'valid': record['valid'], 'score': record['score'], 'build_cost': record.get('build_cost'),
              'metric': 'target items present in the native core after fixed ticks', **timing,
              'source': source, 'files': {n: digest((out / n).read_bytes()) for n in ('task.json', 'blueprint.json', 'record.json')}}
    save(out / 'result.json', result)
    payload = json.dumps({'task': task, 'record': record}, ensure_ascii=False).replace('<', '\\u003c')
    (out / 'replay.html').write_text((PACKAGE / 'replay.html').read_text().replace('__PAYLOAD__', payload))
    return result


def verify(out):
    out = Path(out); result = read(out / 'result.json')
    if result.get('protocol') != manifest()['evaluation_protocol']:
        raise ValueError('evaluation protocol changed; use the matching archived evaluator for historical results')
    if result['source'] != fingerprints():
        raise ValueError('evaluator, runtime, tasks, or engine changed')
    expected_names = {'task.json', 'blueprint.json', 'record.json'}
    if set(result['files']) != expected_names or result['files'] != {n: digest((out / n).read_bytes()) for n in expected_names}:
        raise ValueError('evaluation artifacts changed')
    record, _ = simulate_bytes(read(out / 'task.json'), read_candidate(out / 'blueprint.json'))
    if record != read(out / 'record.json'):
        raise ValueError('fresh engine replay differs')
    if any(result[k] != record.get(k) for k in ('valid', 'score', 'build_cost')):
        raise ValueError('score or validity changed')
    verification = {'valid': True, 'frames': len(record.get('frames', [])),
                    'delivery_events': len(record.get('deliveries', [])),
                    'method': 'fresh JVM; all delivery events and complete sampled inventories/efficiencies compared'}
    save(out / 'verification.json', verification)
    return verification


def tasks():
    return [read(p) for p in sorted((PACKAGE / 'tasks').glob('*.json'))]


def task_path(name):
    paths = {t['id']: PACKAGE / 'tasks' / (t['id'] + '.json') for t in tasks()}
    if name not in paths:
        raise ValueError('unknown task: ' + name)
    return paths[name]
