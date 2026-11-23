import hashlib,json,os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(tmp,p)
def digest(value):return hashlib.sha256(value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def file_hashes(path):
    p=Path(path)
    if p.is_file():return {p.name:digest(p.read_bytes())}
    return {str(f.relative_to(p)):digest(f.read_bytes()) for f in sorted(p.rglob('*')) if f.is_file() and not f.is_symlink() and '__pycache__' not in f.parts}
def immutable(path,value):
    save(path,{'value':value,'sha256':digest(value)})
def load_immutable(path):
    d=read(path)
    if digest(d['value'])!=d['sha256']:raise ValueError('manifest integrity check failed: '+str(path))
    return d['value']
def safe_id(value):
    import re
    if not isinstance(value,str) or not re.fullmatch('[a-z0-9][a-z0-9_.-]{0,90}',value):raise ValueError('invalid identifier')
    return value
