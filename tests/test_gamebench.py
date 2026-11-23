import json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from gamebench import adapters, cohort, workspace
from gamebench.common import read, save, immutable, load_immutable, digest, file_hashes


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.systems=[]
        for name in ('agent-a','agent-b'):
            p=self.root/(name+'.json');save(p,{'id':name,'harness':'test-native','harness_version':'1','model':'none','command':[]});self.systems.append(p)

    def create(self,tasks=('celeste-100m',),profile='smoke'):
        root=self.root/'cohort';cohort.create(root,tasks,self.systems,profile);return root

    def cheap_prepare(self,root,system,t,repeat=0):
        with patch.object(workspace,'public_sources'):
            return workspace.prepare(root,system,t,repeat)

    def test_all_submissions_freeze_before_test_generation(self):
        root=self.create(('2048-policy','showdown-policy'))
        for s,t,r in cohort.members(cohort.manifest(root)):
            self.cheap_prepare(root,s,t,r)
        with self.assertRaisesRegex(ValueError,'all registered'):cohort.seal(root)
        self.assertFalse((root/'private/tests.json').exists())
        for s,t,r in cohort.members(cohort.manifest(root)):cohort.freeze_run(root,s,t,r)
        cohort.seal(root)
        dev=load_immutable(root/'development.json');test=load_immutable(root/'private/tests.json')
        self.assertFalse({x['key'] for x in dev['2048-policy/0']['cases']+dev['2048-policy/0']['validation_cases']} & {x['key'] for x in test['2048-policy/0']['cases']})
        from showdownbench_v3.suite import team_key
        pools=[{team_key(x['team']) for x in dev['showdown-policy/0'][k]} for k in ('teams','validation_teams')]
        pools.append({team_key(x['team']) for x in test['showdown-policy/0']['teams']})
        for i in range(3):
            for j in range(i):self.assertFalse(pools[i]&pools[j])
        with self.assertRaisesRegex(ValueError,'already sealed'):cohort.seal(root)
        with self.assertRaisesRegex(ValueError,'already frozen'):cohort.freeze_run(root,'agent-a','2048-policy',0)

    def test_identical_public_material_across_systems(self):
        root=self.create()
        for s in ('agent-a','agent-b'):self.cheap_prepare(root,s,'celeste-100m')
        a=load_immutable(root/'runs/agent-a/celeste-100m/0/prepared.json')
        b=load_immutable(root/'runs/agent-b/celeste-100m/0/prepared.json')
        self.assertEqual(a['public_files'],b['public_files'])
        text=(root/'runs/agent-a/celeste-100m/0/work/instructions.md').read_text()
        self.assertNotIn('8192 output',text);self.assertIn('last on-disk submission',text)

    def test_changed_task_baseline_budget_or_data_rejected(self):
        root=self.create();m=cohort.manifest(root)
        with patch.object(cohort,'fingerprint',return_value={'changed':'baseline'}):
            with self.assertRaisesRegex(ValueError,'baseline or judge'):cohort.manifest(root)
        with patch.object(cohort,'integration_hashes',return_value={'changed':'budget'}):
            with self.assertRaisesRegex(ValueError,'integration changed'):cohort.manifest(root)
        immutable(root/'development.json',{'changed':True})
        with self.assertRaisesRegex(ValueError,'development data'):cohort.manifest(root)

    def test_all_repeats_required_and_system_identity_not_a_gate(self):
        root=self.create(profile='30m');m=cohort.manifest(root)
        rows=[]
        for s,t,r in cohort.members(m):
            self.cheap_prepare(root,s,t,r);cohort.freeze_run(root,s,t,r)
            rows.append({'system':s,'task_id':t,'repeat':r,'score':100,'baseline':110,'valid_artifact':True})
        sealed=cohort.seal(root)
        report={'cohort_sha256':digest(m),'sealed_sha256':digest(sealed),'rows':rows,'label':'test'}
        immutable(root/'report.json',report)
        self.assertEqual(len(cohort.compare(root)['per_task']),2)
        with self.assertRaisesRegex(ValueError,'official ranking unavailable'):cohort.compare(root,official=True)
        report['rows']=rows[:-1];immutable(root/'report.json',report)
        with self.assertRaisesRegex(ValueError,'missing, duplicate'):cohort.compare(root)

    def test_freeze_rejects_links_and_detects_tampering(self):
        source=self.root/'source';adapters.baseline('celeste-100m',source)
        (source/'script.json').unlink();(source/'script.json').symlink_to(self.systems[0])
        with self.assertRaisesRegex(ValueError,'links'):adapters.freeze('celeste-100m',source,self.root/'dest')
        root=self.create();self.cheap_prepare(root,'agent-a','celeste-100m');cohort.freeze_run(root,'agent-a','celeste-100m',0)
        p=root/'runs/agent-a/celeste-100m/0';(p/'artifact/script.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'frozen submission changed'):cohort.frozen(p)

    def test_invalid_submission_retained_in_cohort(self):
        root=self.create();self.cheap_prepare(root,'agent-a','celeste-100m')
        p=root/'runs/agent-a/celeste-100m/0';(p/'work/submission/script.json').write_text('{}')
        r=cohort.freeze_run(root,'agent-a','celeste-100m',0)
        self.assertEqual(r['status'],'invalid_submission');self.assertFalse((p/'artifact').exists())

    def test_credentials_are_provider_agnostic_and_allowlisted(self):
        from gamebench.launch import credential_environment
        (self.root/'.env').write_text('PROVIDER_TEST_KEY=test-only\nUNRELATED_SECRET=not-forwarded\n')
        with patch('gamebench.launch.ROOT',self.root),patch.dict(os.environ,{},clear=True):
            self.assertEqual(credential_environment(['PROVIDER_TEST_KEY']),{'PROVIDER_TEST_KEY':'test-only'})
            self.assertEqual(credential_environment([]),{})

    def test_native_deadline_and_early_exit_are_distinct(self):
        import sys
        from gamebench.launch import launch
        a=read(self.systems[0]);a['command']=[sys.executable,'-c','pass'];save(self.systems[0],a)
        b=read(self.systems[1]);b['command']=[sys.executable,'-c','import time;time.sleep(20)'];save(self.systems[1],b)
        short={**cohort.budget('smoke'),'wall_seconds':0.15}
        with patch.object(cohort,'budget',return_value=short):root=self.create()
        for s in ('agent-a','agent-b'):self.cheap_prepare(root,s,'celeste-100m')
        self.assertEqual(launch(root,'agent-a','celeste-100m')['termination'],'agent_finished')
        self.assertEqual(launch(root,'agent-b','celeste-100m')['termination'],'wall_time_limit')
        self.assertTrue((root/'runs/agent-b/celeste-100m/0/frozen.json').exists())

    def test_failed_tas_gets_failure_score_and_replay_is_verified(self):
        source=self.root/'source';source.mkdir();save(source/'script.json',{'version':1,'segments':[{'frames':1,'buttons':[]}]})
        result=adapters.evaluate('celeste-100m',source,self.root/'eval')
        self.assertEqual(result['primary'],601);self.assertFalse(result['valid_artifact'])
        self.assertTrue(adapters.verify(self.root/'eval')['valid'])
        result['primary']=1;save(self.root/'eval/result.json',result)
        with self.assertRaisesRegex(ValueError,'reported metric'):adapters.verify(self.root/'eval')

if __name__=='__main__':unittest.main()
