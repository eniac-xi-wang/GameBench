from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import random
import secrets

from showdownbench import core

TRAIN_TEAMS = 256
VALIDATION_PAIRS = 32
TRAIN_PAIRS = 16
TEST_PAIRS = 96


def fingerprints():
    values=core.fingerprints()
    files=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).with_name('spec.json')]
    files+=list(Path(__file__).with_name('baseline').glob('*.cjs'))
    for p in sorted(files):
        values[str(p.relative_to(core.ROOT))]=core.digest(p.read_bytes())
    return values


def team_key(team):
    """Order-independent species combination, so reordered teams cannot cross splits."""
    return '|'.join(sorted(p['species'] for p in team))


def draw_teams(count, excluded=(), salt=None):
    rng=random.Random(salt if salt is not None else secrets.token_hex(32))
    catalog=[p for t in json.loads((core.ROOT/'showdownbench/data/teams.json').read_text()) for p in t['team']]
    assert len({p['species'] for p in catalog})==len(catalog)
    seen=set(excluded);teams=[]
    for _ in range(100000):
        team=deepcopy(rng.sample(catalog,6));key=team_key(team)
        if key in seen:continue
        seen.add(key);teams.append({'id':'mix-'+core.digest(key.encode())[:16],'team':team})
        if len(teams)==count:return teams
    raise ValueError('could not construct enough distinct teams')


def make_suite(teams,pairs=TRAIN_PAIRS,repeats=1,salt=None):
    if type(pairs) is not int or pairs<1 or 2*pairs>len(teams):raise ValueError('not enough distinct teams')
    if type(repeats) is not int or repeats<1:raise ValueError('positive repeat count required')
    rng=random.Random(salt if salt is not None else secrets.token_hex(32))
    chosen=rng.sample(teams,2*pairs)
    commit='965a535ef892d13cd68cf75c076db26f9f32842a'
    rows=[]
    for i in range(pairs):
        a,b=deepcopy(chosen[2*i:2*i+2])
        rng.shuffle(a['team']);rng.shuffle(b['team'])
        # Bootstrap clusters include every opponent/repeat for this team pair.
        block=f'pair-{i:04d}'
        for opponent in core.OPPONENTS:
            for repeat in range(repeats):
                seed='sodium,'+f'{rng.getrandbits(128):032x}'
                for own,foe in ((a,b),(b,a)):
                    for side in ('p1','p2'):
                        first,second=(own,foe) if side=='p1' else (foe,own)
                        rows.append(dict(id=f'game-{len(rows)+1:04d}',block=block,opponent=opponent,
                            formatid='gen9ou',seed=seed,engine_commit=commit,candidate_side=side,
                            team_ids=[first['id'],second['id']],team1=deepcopy(first['team']),team2=deepcopy(second['team'])))
    return rows


def paired_difference(left,right):
    groups={}
    assert len(left)==len(right)
    for a,b in zip(sorted(left,key=lambda r:r['id']),sorted(right,key=lambda r:r['id']),strict=True):
        assert (a['id'],a['block'],a['config'],a['candidate_side'])==(b['id'],b['block'],b['config'],b['candidate_side'])
        groups.setdefault(a['block'],[]).append(b['score']-a['score'])
    means=[sum(v)/len(v) for v in groups.values()];rng=random.Random(1729)
    samples=sorted(sum(rng.choices(means,k=len(means)))/len(means) for _ in range(5000))
    return {'score_delta':sum(means)/len(means),'paired_team_pair_ci95':[samples[124],samples[4874]],'team_pairs':len(means)}


def records(folder):return [json.loads(p.read_text()) for p in sorted((Path(folder)/'games').glob('game-*.json'))]


def public_summary(result):
    return {k:result[k] for k in ('score','score_ci95','games','blocks','by_opponent','wins','draws','failures','turn_limits','mean_turns')}
