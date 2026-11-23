"""Export a recorded Mindustry factory to a v160.7 desktop save and load-test it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mindbench import core


def export(engine, output):
    if output.suffix != '.msav' or output.exists():
        raise ValueError('Choose a new .msav output file')
    result = core.read(engine/'result.json')
    if result['protocol'] != core.manifest()['evaluation_protocol'] or not result['valid']:
        raise ValueError('Requires a valid v3 factory evaluation')
    for name in ('task.json', 'blueprint.json'):
        if hashlib.sha256((engine/name).read_bytes()).hexdigest() != result['files'][name]:
            raise ValueError('Recorded input changed: '+name)
    classes = core.build()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        request = root/'world.json'
        request.write_text(json.dumps({'task':core.read(engine/'task.json'), 'blueprint':core.read(engine/'blueprint.json')}))
        cp = os.pathsep.join(map(str, (classes, core.JAR)))
        subprocess.run([core.JAVA_HOME/'bin/javac','--release','17','-cp',cp,'-d',root,
                        ROOT/'tools/MindustrySave.java'], check=True)
        save = root/'factory.msav'
        for mode in ('save','check'):
            runtime = root/mode
            runtime.mkdir()
            subprocess.run([core.JAVA_HOME/'bin/java','-Xmx512m','-XX:ActiveProcessorCount=1',
                            '-cp',str(root)+os.pathsep+cp,'MindustrySave',mode,request,save,runtime],
                           cwd=runtime, check=True, timeout=90)
        with output.open('xb') as dest, save.open('rb') as src:
            shutil.copyfileobj(src, dest)
    print(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('engine',type=Path,help='engine directory containing result.json, task.json and blueprint.json')
    parser.add_argument('output',type=Path)
    opts=parser.parse_args()
    try:export(opts.engine.resolve(),opts.output)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as e:parser.exit(1,str(e)+'\n')
