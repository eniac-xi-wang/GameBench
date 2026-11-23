"""Export a standalone replay using local shapez PNGs and the pinned simulation."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'shapebench_v2'


def export(engine, task_id, game, output):
    if task_id not in {'paint','stack','cut_rotate'}:
        raise ValueError('Choose cut_rotate, paint or stack')
    result=json.loads((engine/'result.json').read_text())
    def verified(file,checksum):
        data=file.read_bytes()
        if sha256(data).hexdigest()!=checksum:
            raise ValueError(f'Recorded file changed: {file.name}')
        return json.loads(data)
    tasks=verified(engine/'tasks.json',result['task_sha256'])
    task=next(t for t in tasks if t['id']==task_id)
    name=task_id+'.json'
    record=verified(engine/'records'/name,result['record_sha256'][name])
    blueprint=verified(engine/'candidate'/name,result['candidate_hashes'][name])
    if not record['valid']:
        raise ValueError('The recorded layout was rejected by the engine')
    keys=set()
    for b in record['layout']:
        kind=b['type'];variant=b.get('variant','default');rv=b.get('rotationVariant',0)
        if not all(re.fullmatch('[a-z_-]+[0-9]*',v) for v in (kind,variant)):
            raise ValueError('Invalid sprite name')
        suffix='' if variant=='default' else '-'+variant
        if kind=='belt':
            turn=['forward','left','right'][rv]
            keys.update(f'belt/built/{turn}_{i}' for i in range(14))
        elif kind=='underground_belt':
            keys.add('buildings/underground_belt_'+['entry','exit'][rv]+suffix)
        else:keys.add('buildings/'+kind+suffix)
    sprites=game/'res_raw/sprites'
    keys.update('colors/'+f.stem for f in (sprites/'colors').glob('*.png'))
    textures={k:'data:image/png;base64,'+base64.b64encode((sprites/(k+'.png')).read_bytes()).decode() for k in sorted(keys)}
    payload=dict(task=task,blueprint=blueprint,expected=record['deliveries'],textures=textures)
    html=Path(__file__).with_name('shapez-player.html').read_text()
    for token,file in [('__VENDOR__',PACKAGE/'vendor/engine.cjs'),('__ENGINE__',PACKAGE/'engine.cjs')]:
        html=html.replace(token,re.sub(r'</script',r'<\\/script',file.read_text(),flags=re.I))
    with output.open('x',encoding='utf-8') as dest:
        dest.write(html.replace('__PAYLOAD__',json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('engine',type=Path);p.add_argument('task',choices=['cut_rotate','paint','stack'])
    p.add_argument('output',type=Path);p.add_argument('--game-dir',type=Path,default=ROOT/'shapez')
    a=p.parse_args()
    try:export(a.engine,a.task,a.game_dir,a.output)
    except (ValueError,KeyError,OSError) as e:p.exit(1,str(e)+'\n')
