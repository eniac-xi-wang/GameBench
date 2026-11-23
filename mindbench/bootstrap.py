"""Install pinned official binaries locally; never change system Java."""
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from . import core as c


from gamebench.setup import fetch as download


def setup():
    m = c.manifest()
    game = c.ROOT / 'mindustry'
    if not game.exists():
        subprocess.run(['git', 'clone', '--depth', '1', '--branch', m['tag'], m['repository'] + '.git', str(game)], check=True)
    commit = subprocess.check_output(['git', '-C', str(game), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != m['commit']: raise RuntimeError('source checkout does not match pinned release')
    download(m['server_url'], c.JAR, m['server_sha256'])
    if not (c.JAVA_HOME / 'bin/java').exists():
        if (platform.system(), platform.machine()) != ('Darwin', 'arm64'):
            raise RuntimeError('Set MINDBENCH_JAVA_HOME to a local JDK 17+; automatic JDK installation supports macOS arm64')
        archive = c.ROOT / '.tools/downloads/mindustry-jdk21.tar.gz'
        download(m['jdk_url'], archive, m['jdk_archive_sha256'])
        c.RUNTIME.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=c.RUNTIME) as temp:
            with tarfile.open(archive) as tar: tar.extractall(temp, filter='data')
            source = next(Path(temp).iterdir())
            source.rename(c.RUNTIME / 'jdk')
    classes = c.build()
    result, _ = c.run({'mode':'catalog'})
    if result != c.read(c.PACKAGE / 'catalog.json'): raise RuntimeError('engine catalog mismatch')
    return {'ready':True,'release':m['tag'],'source_commit':commit,'compiled_adapter':str(classes)}


if __name__ == '__main__': print(json.dumps(setup()))
