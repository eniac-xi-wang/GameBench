import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from gamebench import expanded
from gamebench.common import ROOT, load_immutable, read, save


class PublicReleaseTests(unittest.TestCase):
    def test_expanded_research_draw_uses_new_teams_and_balanced_blocks(self):
        final = expanded.final(smoke=False)
        self.assertEqual(len(final['cases']), 1920)
        counts = Counter(c['block'] for c in final['cases'])
        self.assertEqual(len(counts), 96)
        self.assertEqual(set(counts.values()), {20})
        seen = set(read(expanded.DATA/'used-smoke-keys.json'))
        for group in ('train','validation','final'):
            teams = final['teams'] if group=='final' else read(expanded.DATA/(group+'.json'))
            for p in expanded.profiles():
                for t in teams[p['id']]:
                    key = p['formatid']+'/'+t['species_key']
                    self.assertNotIn(key, seen)
                    seen.add(key)

    def test_native_agent_edits_and_requests_two_dev_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            script = folder/'agent.py'
            script.write_text(
                "import json, subprocess, sys\n"
                "from pathlib import Path\n"
                "p=Path('submission/script.json')\n"
                "timeline=json.loads(p.read_text())\n"
                "for i in (1, 2):\n"
                "    timeline['segments'][0]['frames'] -= 1\n"
                "    p.write_text(json.dumps(timeline))\n"
                "    subprocess.run([sys.executable, 'bench.py', 'dev-'+str(i)], check=True)\n"
            )
            manifest = folder/'system.json'
            save(manifest, dict(id='fixture', harness='local Python process', harness_version='1',
                                model='none', command=['{python}',str(script)]))
            out = folder/'run'
            subprocess.run([sys.executable, str(ROOT/'bench'), '--tasks','celeste-100m',
                            '--system','baseline-replay','--system',str(manifest),'--out',str(out)],
                           cwd=folder, check=True, capture_output=True, text=True)
            work = out/'runs/fixture/celeste-100m/0/work'
            rows = load_immutable(out/'report.json')['rows']
            self.assertEqual([(r['baseline'],r['score']) for r in rows], [(94,94),(94,92)])
            for i in (1,2):
                trial = work/'feedback'/f'dev-{i}'
                self.assertEqual(read(trial/'result.json')['primary'], 94-i)
                self.assertTrue(read(trial/'verification.json')['valid'])
                self.assertTrue((trial/'engine/replay.html').is_file())
            self.assertEqual(rows[1]['execution']['termination'],'agent_finished')
            self.assertTrue((out/rows[1]['replay']).is_file())

    def test_offline_submission_from_another_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            src=folder/'candidate'
            script=read(ROOT/'examples/celeste_100m_baseline.json')
            script['segments'][0]['frames']-=1
            save(src/'script.json',script)
            subprocess.run([sys.executable, str(ROOT/'bench'), '--submission',str(src),'--out','report'],
                           cwd=folder, check=True, capture_output=True, text=True)
            row=load_immutable(folder/'report/report.json')['rows'][0]
            self.assertEqual((row['system'],row['score']),('saved-submission',93))
