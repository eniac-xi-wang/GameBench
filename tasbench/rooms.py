"""Fixed multi-room tasks; legacy 100m scoring remains in core.py unchanged."""
from __future__ import annotations
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from . import core

ROOT=core.ROOT
TASKS=ROOT/'tasks/rooms'
LEGACY_ID='celeste-classic-100m-v1'


def task_file(task_id: str) -> Path:
    files={json.loads(p.read_text())['id']:p for p in TASKS.glob('*.json')}
    if task_id not in files:raise ValueError('unknown fixed room task')
    return files[task_id]


def task(task_id: str) -> dict:
    return json.loads(task_file(task_id).read_text())


def public_task(task_id: str) -> dict:
    data=task(task_id)
    prefix=ROOT/data.pop('bootstrap_file')
    data['bootstrap_sha256']=core.digest(prefix.read_bytes())
    return data


def source_hashes(task_id: str) -> dict:
    data=task(task_id)
    files=['tasbench/rooms.py','tasbench/native/rooms_runner.cpp',str(task_file(task_id).relative_to(ROOT)),data['bootstrap_file']]
    return core.source_hashes()|{f:core.digest((ROOT/f).read_bytes()) for f in files}


def build() -> Path:
    folder=ROOT/'.tas-build';folder.mkdir(exist_ok=True)
    exe=folder/'celeste-rooms-runner';stamp=folder/'rooms-build.json'
    compiler=shutil.which('clang++') or shutil.which('g++')
    if not compiler:raise RuntimeError('C++ compiler required')
    sources=core.source_hashes()|{'tasbench/native/rooms_runner.cpp':core.digest((ROOT/'tasbench/native/rooms_runner.cpp').read_bytes())}
    metadata={'sources':sources,'compiler':subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],
              'flags':['-std=gnu++20','-O2','-fwrapv','-Wno-narrowing']}
    with (folder/'rooms-build.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        old=json.loads(stamp.read_text()) if stamp.exists() else {}
        if not exe.exists() or any(old.get(k)!=v for k,v in metadata.items()) or old.get('binary_sha256')!=core.digest(exe.read_bytes()):
            subprocess.run([compiler,*metadata['flags'],str(ROOT/'tasbench/native/rooms_runner.cpp'),'-o',str(exe)],check=True,capture_output=True,text=True)
            metadata['binary_sha256']=core.digest(exe.read_bytes());core.save_json(stamp,metadata)
    return exe


def provenance(task_id):
    build()
    return {'build':json.loads((ROOT/'.tas-build/rooms-build.json').read_text()),'task_sources':source_hashes(task_id)}


def simulate(masks: list[int],out: Path,task_id: str) -> dict:
    data=task(task_id);exe=build()
    out.mkdir(parents=True,exist_ok=True)
    (out/'inputs.txt').write_text('\n'.join(map(str,masks))+'\n')
    p=subprocess.run([str(exe),'--run',str(ROOT/'celeste-classic/data'),str(ROOT/data['bootstrap_file']),
                      str(out/'inputs.txt'),str(out),str(data['room_index'])],capture_output=True,text=True,check=True,timeout=15)
    lines=p.stdout.splitlines();reports=[json.loads(line) for line in lines if line.startswith('{"success":')]
    if len(reports)!=1:raise RuntimeError('invalid native evaluator response')
    (out/'engine-diagnostics.txt').write_text('\n'.join(line for line in lines if not line.startswith('{"success":')))
    return reports[0]


def evaluate(script: dict,out: Path,task_id: str) -> dict:
    masks=core.parse_script(script)
    if out.exists():raise ValueError('output already exists')
    out.mkdir(parents=True)
    core.save_json(out/'script.json',core.encode_script(masks))
    report=simulate(masks,out,task_id)
    report.update({'task':task_id,'completion_frames':report['frames'] if report['success'] else None,
                   'seconds':report['frames']/30,'script_frames':len(masks),'script_sha256':core.digest(bytes(masks)),
                   'trace_sha256':core.digest((out/'trace.jsonl').read_bytes()),'video_sha256':core.digest((out/'frames.bin').read_bytes()),
                   'provenance':provenance(task_id)})
    core.save_json(out/'result.json',report);core.make_replay(out,report)
    replay=out/'replay.html';replay.write_text(replay.read_text().replace('100m TAS',str(task(task_id)['altitude_m'])+'m TAS'))
    return report


def verify(out: Path) -> dict:
    saved=json.loads((out/'result.json').read_text());task_id=saved['task']
    if saved['provenance']!=provenance(task_id):raise ValueError('room evaluator provenance changed')
    masks=core.parse_script(json.loads((out/'script.json').read_text()))
    with tempfile.TemporaryDirectory(prefix='room-verify-') as tmp:
        result=simulate(masks,Path(tmp),task_id)
        checks={'script':core.digest(bytes(masks))==saved['script_sha256'],
                'recorded_trace':core.digest((out/'trace.jsonl').read_bytes())==saved['trace_sha256'],
                'recorded_video':core.digest((out/'frames.bin').read_bytes())==saved['video_sha256'],
                'fresh_trace':core.digest((Path(tmp)/'trace.jsonl').read_bytes())==saved['trace_sha256'],
                'fresh_video':core.digest((Path(tmp)/'frames.bin').read_bytes())==saved['video_sha256'],
                'result':all(saved[k]==v for k,v in result.items()),
                'completion':saved['completion_frames']==(result['frames'] if result['success'] else None)}
    if not all(checks.values()):raise ValueError('room replay verification failed: '+str(checks))
    return {'valid':True,'success':saved['success'],'completion_frames':saved['completion_frames'],'checks':checks}


class BatchSimulator:
    """Trusted baseline-building helper; every trial starts from an exact OS process copy."""
    def __init__(self,task_id):
        data=task(task_id)
        self.process=subprocess.Popen([str(build()),'--batch',str(ROOT/'celeste-classic/data'),str(ROOT/data['bootstrap_file']),str(data['room_index'])],
                                      stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
    def run(self,masks):
        core.parse_script(core.encode_script(masks))
        self.process.stdin.write(' '.join(map(str,masks))+'\n');self.process.stdin.flush()
        while True:
            line=self.process.stdout.readline()
            if not line:raise RuntimeError('batch simulator exited: '+self.process.stderr.read()[-1000:])
            if line.startswith('{"success":'):return json.loads(line)
    def close(self):
        self.process.stdin.close()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.process.stdout.close();self.process.stderr.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
