"""Fetch only pinned public prerequisites for the selected games."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

from .common import ROOT, read, save


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(url, dest, checksum):
    if dest.is_file() and sha(dest) == checksum:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    cache = os.environ.get('GAMEBENCH_DOWNLOAD_CACHE')
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as stream:
        temp = Path(stream.name)
    try:
        cached = Path(cache) / dest.name if cache else None
        if cached and cached.is_file():
            shutil.copyfile(cached, temp)
        else:
            urllib.request.urlretrieve(url, temp)
        if sha(temp) != checksum:
            raise ValueError(f'Checksum mismatch for {dest.name}')
        temp.replace(dest)
    finally:
        temp.unlink(missing_ok=True)


def checkout(spec):
    dest = ROOT / spec['path']
    if not dest.exists():
        cache = os.environ.get('GAMEBENCH_SOURCE_CACHE')
        source = Path(cache) / dest.name if cache else None
        with tempfile.TemporaryDirectory(dir=ROOT / '.tools') as tmp:
            tree = Path(tmp) / 'checkout'
            subprocess.run(['git', 'init', '-q', str(tree)], check=True)
            git = ['git', '-C', str(tree)]
            subprocess.run([*git, 'remote', 'add', 'origin', spec['url']], check=True)
            subprocess.run([*git, 'fetch', '-q', '--depth=1', str(source) if source and source.is_dir() else 'origin', spec['commit']], check=True)
            subprocess.run([*git, 'checkout', '-q', '--detach', 'FETCH_HEAD'], check=True)
            tree.rename(dest)
    git = ['git', '-C', str(dest)]
    if (subprocess.check_output([*git, 'rev-parse', 'HEAD'], text=True).strip() != spec['commit']
            or subprocess.check_output([*git, 'status', '--porcelain', '--untracked-files=no'])):
        raise ValueError(f'Expected unmodified upstream commit in {dest}')


def node():
    system = platform.system().lower()
    arch = {'aarch64':'arm64', 'arm64':'arm64', 'x86_64':'x64'}.get(platform.machine())
    filename = f'node-v24.22.3-{system}-{arch}.tar.gz'
    checksums = read(ROOT / 'benchmarks/node.json')
    if filename not in checksums:
        raise ValueError(f'No pinned Node archive for {system} {arch}')
    tools = ROOT / '.tools'
    dest = tools / 'node'
    if not dest.exists():
        archive = tools / 'downloads' / filename
        fetch('https://nodejs.org/dist/v24.22.3/' + filename, archive, checksums[filename])
        with tempfile.TemporaryDirectory(dir=tools) as tmp, tarfile.open(archive) as tar:
            tar.extractall(tmp, filter='data')
            (Path(tmp) / filename.removesuffix('.tar.gz')).rename(dest)
    if subprocess.check_output([dest/'bin/node', '--version'], text=True).strip() != 'v24.22.3':
        raise ValueError('Unexpected installed Node version')
    return dict(os.environ, PATH=str(dest/'bin') + os.pathsep + os.environ['PATH'])


def celeste():
    from tasbench.core import encode_script
    data = (ROOT/'celeste-classic/test-tas.txt').read_text().strip().strip(',')
    inputs = [int(n) for n in data.split(',')]
    for r in read(ROOT/'benchmarks/tas-inputs.json'):
        start = r['offset']
        path = ROOT/r['file']
        save(path, encode_script(inputs[start:start+r['frames']]))
        if sha(path) != r['sha256']:
            raise ValueError(f'Unexpected TAS baseline {path.name}')
        if start:
            prefix = ROOT/f"tasks/room_prefixes/{r['altitude']}m.txt"
            prefix.parent.mkdir(exist_ok=True)
            prefix.write_text(''.join(f'{n}\n' for n in inputs[:start]))


def npm_build(folder, env, build, outputs):
    lock = folder/'package-lock.json'
    stamp = ROOT/'.tools'/('npm-' + folder.name + '.json')
    key = {'lock':sha(lock), 'node':'24.22.3'}
    if folder.name == 'tools':
        key.update({n:sha(ROOT/'shapebench_v2'/n) for n in ['build.cjs','upstream-entry.js']})
    if stamp.exists() and read(stamp) == key and all(p.exists() for p in outputs):
        return
    subprocess.run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=folder, env=env, check=True)
    subprocess.run(build, cwd=folder, env=env, check=True)
    save(stamp, key)


def prepare(games):
    (ROOT/'.tools').mkdir(exist_ok=True)
    if games & {'2048','showdown'} and not Path('/usr/bin/sandbox-exec').is_file():
        raise ValueError('2048 and Showdown policy isolation requires macOS with sandbox-exec.')
    sources = read(ROOT/'benchmarks/upstream.json')
    for game in sorted(games):
        print(f'Preparing {game}', flush=True)
        checkout(sources[game])
    if 'celeste' in games:
        celeste()
    if games & {'2048','showdown','shapez'}:
        env = node()
        if 'showdown' in games:
            folder = ROOT/'pokemon-showdown'
            npm_build(folder, env, ['node','build'], [folder/'dist/sim/index.js',folder/'node_modules/ts-chacha20'])
        if 'shapez' in games:
            npm_build(ROOT/'tools', env, ['node',str(ROOT/'shapebench_v2/build.cjs')], [ROOT/'shapebench_v2/vendor/engine.cjs',ROOT/'shapebench_v2/vendor/manifest.json'])
    if 'mindustry' in games:
        from mindbench.bootstrap import setup
        setup()
