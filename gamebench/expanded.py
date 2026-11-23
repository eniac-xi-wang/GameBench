"""Six equally weighted Showdown strata, five opponents and four side/ownership swaps."""
import random
import secrets
import subprocess
import tempfile
from pathlib import Path

from .common import ROOT, read, save
from showdownbench import core

DATA = ROOT/'expanded'
OPPONENTS = ('damage', 'heuristic', 'hazard-control', 'setup-pressure', 'anti-setup')


def profiles():
    return read(DATA/'distribution.json')['profiles']


def cases(teams, salt, pairs):
    rows = []
    commit = read(ROOT/'benchmarks/upstream.json')['showdown']['commit']
    for profile in profiles():
        name = profile['id']
        roster = list(teams[name])
        if not 1 <= pairs <= len(roster)//2:
            raise ValueError(f'Insufficient teams in {name}')
        random.Random(salt+'/'+name).shuffle(roster)
        for pair in range(pairs):
            a, b = roster[2*pair:2*pair+2]
            block = f'{name}/pair-{pair}'
            for opponent in OPPONENTS:
                seed = 'sodium,' + core.digest(f'{salt}/{block}/{opponent}'.encode())[:32]
                for own, foe in ((a,b), (b,a)):
                    for side in ('p1','p2'):
                        first, second = (own,foe) if side == 'p1' else (foe,own)
                        rows.append(dict(id=f'game-{len(rows)+1:05d}', block=block,
                            opponent=opponent, candidate_side=side, formatid=profile['formatid'],
                            seed=seed, engine_commit=commit, team_ids=[first['id'],second['id']],
                            team1=first['team'], team2=second['team']))
    return rows


def development(salt):
    return {'cases':cases(read(DATA/'train.json'), salt, 1),
            'validation_cases':cases(read(DATA/'validation.json'), salt+'/validation', 1)}


def final(smoke):
    pairs = 1 if smoke else 16
    excluded = set(read(DATA/'used-smoke-keys.json'))
    for split in ('train','validation'):
        teams = read(DATA/(split+'.json'))
        for profile in profiles():
            excluded.update(profile['formatid']+'/'+t['species_key'] for t in teams[profile['id']])
    salt = secrets.token_hex(32)
    with tempfile.TemporaryDirectory() as tmp:
        request = Path(tmp)/'request.json'
        result = Path(tmp)/'result.json'
        save(request, dict(catalog=read(DATA/'set-bank.json'), counts={'final':pairs*2},
                           seed=salt, excluded=sorted(excluded)))
        subprocess.run([core.NODE, ROOT/'tasklab/showdown_pool/generate.cjs', 'sample', result, request], check=True)
        teams = read(result)['splits']['final']
    return {'teams':teams, 'cases':cases(teams, salt+'/battles', pairs)}


def paired(left, right):
    from collections import defaultdict
    blocks = defaultdict(list)
    for a,b in zip(sorted(left,key=lambda r:r['id']), sorted(right,key=lambda r:r['id']), strict=True):
        if any(a[k]!=b[k] for k in ('id','opponent','block','config','candidate_side','team_ids')):
            raise ValueError('Programs faced different scenarios')
        blocks[a['block']].append(b['score']-a['score'])
    strata = defaultdict(list)
    for block, values in blocks.items():
        strata[block.split('/')[0]].append(sum(values)/len(values))
    rng = random.Random(1729)
    samples = sorted(sum(sum(rng.choices(v,k=len(v)))/len(v) for v in strata.values())/len(strata)
                     for _ in range(5000))
    return {'score_delta':sum(sum(v)/len(v) for v in strata.values())/len(strata),
            'paired_team_pair_ci95':[samples[124],samples[4874]], 'team_pairs':len(blocks),
            'strata':len(strata),'method':'conditional stratified team-pair bootstrap'}
