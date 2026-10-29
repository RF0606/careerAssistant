import copy
import importlib.util
import tempfile
import unittest
import json
import subprocess
import sys
from unittest.mock import patch
from pathlib import Path
from fixtures import make_workspace,assessment,draft,stub_ready_package,authorized_preparation
from storage import Store,SCHEMA,digest,slug,atomic
import profiles,jobs,resume

PROJECT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('installer',PROJECT/'install.py'); installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.s=make_workspace(Path(self.temp.name)/'person-a')
        jobs.assess(self.s,assessment(self.s))

    def ready(self):
        stub_ready_package(self.s)
        return authorized_preparation(self.s)

    def test_initialization_resumes_without_wiping(self):
        profiles.checkpoint(self.s,'environment')
        before=self.s.read('profile.json')
        self.s.initialize()
        self.assertEqual(before,self.s.read('profile.json'))
        self.assertEqual('materials',self.s.status()['next_step'])

    def test_isolated_profiles_and_roles(self):
        b=make_workspace(Path(self.temp.name)/'person-b','software')
        self.assertNotEqual(self.s.read('profile.json')['facts']['name'],b.read('profile.json')['facts']['name'])
        wrapper=(b.workspace/'.agents/skills/career-resume-software/SKILL.md').read_text()
        self.assertNotIn('Riley Stone',wrapper); self.assertNotIn('Morgan Reed',wrapper)

    def test_confirmed_fact_needs_correction_authorization(self):
        fact=copy.deepcopy(self.s.read('profile.json')['facts']['name']);fact['text']='Corrected fictional name'
        with self.assertRaises(ValueError):profiles.update_profile(self.s,{'facts':{'name':fact}})
        profiles.update_profile(self.s,{'facts':{'name':fact},'change_confirmation':'User corrects spelling'})
        self.assertEqual(fact['text'],self.s.read('profile.json')['facts']['name']['text'])

    def test_unconfirmed_fact_cannot_support_positive_score(self):
        fact=copy.deepcopy(self.s.read('profile.json')['facts']['skills']);fact['status']='unconfirmed'
        profiles.update_profile(self.s,{'facts':{'skills':fact},'change_confirmation':'Fixture marks this unknown'})
        with self.assertRaises(ValueError):jobs.assess(self.s,assessment(self.s))

    def test_incomplete_jd_not_scorable(self):
        a=assessment(self.s);a['job']['full_jd']=False
        with self.assertRaises(ValueError):jobs.assess(self.s,a)

    def test_unknown_eligibility_does_not_pass(self):
        a=assessment(self.s);a['eligibility']=[]
        result=jobs.assess(self.s,a)
        self.assertEqual('unknown',result['eligibility_result'])
        self.assertEqual('Needs user',jobs.add_application(self.s,'demo-job')['status'])

    def test_eligibility_failure_skips_application(self):
        a=assessment(self.s);a['eligibility'][0]['result']='no';jobs.assess(self.s,a)
        with self.assertRaises(ValueError):jobs.add_application(self.s,'demo-job')
        self.assertEqual(0,self.s.read('tracker.json')['record_count'])

    def test_duplicate_normalized_url(self):
        jobs.add_application(self.s,'demo-job')
        a=assessment(self.s,jid='second');a['job']['url']='https://example.invalid/jobs/demo-job?utm_source=testing'
        jobs.assess(self.s,a)
        with self.assertRaises(ValueError):jobs.add_application(self.s,'second')

    def test_cross_employer_requisition_not_a_duplicate(self):
        jobs.add_application(self.s,'demo-job')
        a=assessment(self.s,jid='other',company='Another fictional employer');a['job']['requisition_id']='demo-job';jobs.assess(self.s,a)
        jobs.add_application(self.s,'other')
        self.assertEqual(2,self.s.read('tracker.json')['record_count'])

    def test_same_employer_title_with_distinct_requisitions_is_not_a_duplicate(self):
        jobs.add_application(self.s,'demo-job')
        jobs.assess(self.s,assessment(self.s,'separate-requisition'))
        jobs.add_application(self.s,'separate-requisition')
        self.assertEqual(2,self.s.read('tracker.json')['record_count'])

    def test_matching_requisition_still_blocks_different_urls_and_review(self):
        first=jobs.add_application(self.s,'demo-job')
        other=assessment(self.s,'repost'); other['job']['requisition_id']=' DEMO-JOB '
        jobs.assess(self.s,other)
        review={'job_id':'repost','application_ids':[first['id']],'user_confirmation':'Fixture reviews the position','evidence':'Fictional posting inspected'}
        with self.assertRaisesRegex(ValueError,'Possible duplicate'):
            jobs.add_application(self.s,'repost',review)
        self.assertEqual(1,self.s.read('tracker.json')['record_count'])

    def test_title_only_match_requires_current_job_scoped_user_review(self):
        first=jobs.add_application(self.s,'demo-job')
        other=assessment(self.s,'separate-position'); other['job'].pop('requisition_id')
        jobs.assess(self.s,other)
        before=self.s.read('tracker.json')
        with self.assertRaisesRegex(ValueError,'review-input'):
            jobs.add_application(self.s,'separate-position')
        review={'job_id':'wrong-job','application_ids':[first['id']],'user_confirmation':'Fictional user confirms a separate position','evidence':'Fictional source shows a different location and team'}
        with self.assertRaises(ValueError): jobs.add_application(self.s,'separate-position',review)
        self.assertEqual(before,self.s.read('tracker.json'))
        review['job_id']='separate-position'
        row=jobs.add_application(self.s,'separate-position',review)
        self.assertEqual(review['user_confirmation'],row['duplicate_review']['user_confirmation'])
        self.assertIn('reviewed_at',row['duplicate_review'])

    def test_ambiguous_duplicate_review_cannot_bypass_unknown_attempt(self):
        app,_,review=self.ready(); jobs.prepare(self.s,app['id'],review); jobs.begin_submit(self.s,app['id'])
        other=assessment(self.s,'possibly-reposted'); other['job'].pop('requisition_id')
        jobs.assess(self.s,other)
        approval={'job_id':'possibly-reposted','application_ids':[app['id']],'user_confirmation':'Fictional review','evidence':'Fictional evidence'}
        with self.assertRaisesRegex(ValueError,'uncertain submission'):
            jobs.add_application(self.s,'possibly-reposted',approval)
        self.assertEqual(1,self.s.read('tracker.json')['record_count'])

    def test_duplicate_review_cli_accepts_only_the_reviewed_job(self):
        first=jobs.add_application(self.s,'demo-job')
        other=assessment(self.s,'reviewed-job'); other['job'].pop('requisition_id')
        jobs.assess(self.s,other)
        path=self.s.root/'duplicate-review.json'
        atomic(path,{'job_id':'reviewed-job','application_ids':[first['id']],'user_confirmation':'Fictional user confirms separate roles','evidence':'Reviewed different fictional teams'})
        result=subprocess.run([sys.executable,str(PROJECT/'skills/career-assistant/scripts/career.py'),'--workspace',str(self.s.workspace),'application-add','reviewed-job','--review-input',str(path)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual('reviewed-job',json.loads(result.stdout)['duplicate_review']['job_id'])

    def test_invalid_preference_shapes_never_change_saved_data_or_history(self):
        before=(self.s.root/'preferences.json').read_bytes()
        history=list((self.s.root/'history/events').glob('*.json'))
        invalid=[None,[],{'targets':None},{'targets':'operations'},{'targets':[None]},{'targets':[{}]},
                 {'targets':[{'id':[]}]},{'targets':[{'title':12}]},{'targets':[{'title':'Operations','priority':True}]},
                 {'locations':[None]},{'work_modes':'remote'},{'work_authorization':{}},{'work_authorization':[{}]},
                 {'compensation':None},{'contracts':{}},{'exclusions':[12]},{'start_date':[]},
                 {'submission_policy':[]},{'include_projects':'false'},{'travel':[]},{'commute':[]}]
        for update in invalid:
            with self.subTest(update=update), self.assertRaises(ValueError): profiles.update_preferences(self.s,update)
            self.assertEqual(before,(self.s.root/'preferences.json').read_bytes())
        self.assertEqual(history,list((self.s.root/'history/events').glob('*.json')))
        self.assertIn('next_step',self.s.status())

    def test_legacy_invalid_preferences_can_be_repaired_without_reset(self):
        before=self.s.read('preferences.json'); facts=self.s.read('profile.json')
        atomic(self.s.root/'preferences.json',{**before,'targets':None})
        with self.assertRaisesRegex(ValueError,'preferences.targets'): self.s.status()
        profiles.update_preferences(self.s,{'targets':before['targets']})
        after=self.s.read('preferences.json')
        self.assertEqual(before['revision']+1,after['revision'])
        self.assertEqual(before['locations'],after['locations'])
        self.assertEqual(before['targets'],after['targets'])
        self.assertEqual(facts,self.s.read('profile.json'))
        self.assertIn('next_step',self.s.status())

    def test_preference_change_invalidates_assessment(self):
        profiles.update_preferences(self.s,{'locations':['Elsewhere']})
        with self.assertRaises(ValueError):jobs.add_application(self.s,'demo-job')

    def test_policy_change_invalidates_existing_grant(self):
        a,g,r=self.ready();jobs.prepare(self.s,a['id'],r)
        profiles.update_preferences(self.s,{'submission_policy':'per-application'})
        with self.assertRaises(ValueError):jobs.begin_submit(self.s,a['id'])

    def test_batch_cap_includes_uncertain_clicks(self):
        a,g,r=self.ready();jobs.prepare(self.s,a['id'],r);jobs.begin_submit(self.s,a['id'])
        jobs.assess(self.s,assessment(self.s,'other-job','Other Fictional Company'))
        stub_ready_package(self.s,'other-job')
        other=jobs.add_application(self.s,'other-job')
        # Scope remains explicit; extend only the unit fixture, keeping its cap of one.
        data=self.s.read('grants.json');data['grants'][0]['job_ids'].append('other-job');self.s.write('grants.json',data)
        with self.assertRaises(ValueError):jobs.prepare(self.s,other['id'],r)

    def test_profile_changed_after_preparation_blocks_click(self):
        a,g,r=self.ready();jobs.prepare(self.s,a['id'],r)
        fact=copy.deepcopy(self.s.read('profile.json')['facts']['name']);fact['text']='Another fictional spelling'
        profiles.update_profile(self.s,{'facts':{'name':fact},'change_confirmation':'User correction'})
        with self.assertRaises(ValueError):jobs.begin_submit(self.s,a['id'])

    def test_projects_absent_by_default(self):
        resume.render(self.s,'demo-job',draft(self.s),False)
        tex=(self.s.root/'packages/demo-job/resume.tex').read_text()
        self.assertNotIn('\\section{Projects}',tex)

    def test_projects_order_after_user_request(self):
        resume.render(self.s,'demo-job',draft(self.s,True),False)
        tex=(self.s.root/'packages/demo-job/resume.tex').read_text()
        self.assertLess(tex.index('\\section{Work Experience}'),tex.index('\\section{Projects}'))
        self.assertLess(tex.index('\\section{Projects}'),tex.index('\\section{Education}'))

    def test_project_material_alone_not_permission(self):
        d=draft(self.s,True);d.pop('project_section_request')
        with self.assertRaises(ValueError):resume.render(self.s,'demo-job',d,False)

    def test_missing_claim_evidence_rejected(self):
        d=draft(self.s);d['summary']['evidence_ids']=[]
        with self.assertRaises(ValueError):resume.render(self.s,'demo-job',d,False)

    def test_tex_special_characters_escaped(self):
        escaped=resume.escape('R&D C# 12% data_quality {x} $')
        for token in [r'\&',r'\#',r'\%',r'\_',r'\{',r'\$']:self.assertIn(token,escaped)

    def test_draft_cannot_finish_trial(self):
        for step in ['environment','materials','facts','preferences','roles','automation']:profiles.checkpoint(self.s,step)
        resume.render(self.s,'demo-job',draft(self.s),False)
        with self.assertRaises(ValueError):profiles.checkpoint(self.s,'trial')

    def test_secret_fields_not_accepted_in_profile(self):
        with self.assertRaises(ValueError):self.s.write('extra.json',{'schema_version':SCHEMA,'password':'never-store'})

    def test_single_writer_lock(self):
        with self.s.lock():
            with self.assertRaises(ValueError):
                with self.s.lock():pass

    def test_unknown_schema_preserved_and_rejected(self):
        path=self.s.root/'onboarding.json'; path.write_text('{"schema_version":99}')
        with self.assertRaises(ValueError):self.s.initialize()
        self.assertIn('99',path.read_text())

    def test_slug_cannot_escape_workspace(self):
        with self.assertRaises(ValueError):slug('../outside')

    def test_unresolved_answers_prevent_preparation(self):
        a,g,r=self.ready();r['unresolved_fields']=['authorization']
        with self.assertRaises(ValueError):jobs.prepare(self.s,a['id'],r)

    def test_no_grant_without_chosen_policy(self):
        profiles.update_preferences(self.s,{'submission_policy':None})
        with self.assertRaises(ValueError):jobs.grant(self.s,{'job_ids':['demo-job'],'max_submissions':1,'user_request':'test'})

    def test_per_application_scope_is_one_job(self):
        profiles.update_preferences(self.s,{'submission_policy':'per-application'})
        with self.assertRaises(ValueError):jobs.grant(self.s,{'job_ids':['demo-job'],'max_submissions':2,'user_request':'test'})

    def test_changed_pdf_blocks_click(self):
        a,g,r=self.ready();jobs.prepare(self.s,a['id'],r)
        (self.s.root/'packages/demo-job/resume.pdf').write_bytes(b'changed')
        with self.assertRaises(ValueError):jobs.begin_submit(self.s,a['id'])

    def test_prepared_snapshot_is_preserved_but_rerender_still_blocks_click(self):
        app,_,review=self.ready(); attempt=jobs.prepare(self.s,app['id'],review)
        frozen=self.s.root/attempt['resume_path']; original=frozen.read_bytes()
        resume.render(self.s,'demo-job',draft(self.s),False)
        self.assertEqual(original,frozen.read_bytes())
        with self.assertRaises(ValueError): jobs.begin_submit(self.s,app['id'])
        self.assertNotIn('started_at',self.s.read('tracker.json')['records'][0]['attempts'][0])

    def test_submitted_snapshot_survives_rerender_with_all_original_files(self):
        app,_,review=self.ready(); attempt=jobs.prepare(self.s,app['id'],review)
        directory=self.s.root/attempt['snapshot_path']
        original={p.name:p.read_bytes() for p in directory.iterdir()}
        jobs.begin_submit(self.s,app['id'])
        receipt=self.s.root/'evidence/receipt.txt'; receipt.parent.mkdir(); receipt.write_text('Fictional receipt')
        jobs.outcome(self.s,app['id'],{'attempt_id':attempt['id'],'result':'confirmed','detail':'Fictional mock only','observed_confirmation':True,'confirmation_text':'Received','confirmation_url':'https://example.invalid/thanks','evidence_path':'evidence/receipt.txt','next_action':'Wait'})
        resume.render(self.s,'demo-job',draft(self.s),False)
        self.assertEqual(original,{p.name:p.read_bytes() for p in directory.iterdir()})
        row=self.s.read('tracker.json')['records'][0]
        self.assertEqual('Submitted',row['status'])
        self.assertEqual(attempt['pdf_sha256'],digest((self.s.root/row['attempts'][0]['resume_path']).read_bytes()))

    def test_unknown_snapshot_survives_rerender_and_reconciles_original_attempt(self):
        app,_,review=self.ready(); attempt=jobs.prepare(self.s,app['id'],review); jobs.begin_submit(self.s,app['id'])
        resume.render(self.s,'demo-job',draft(self.s),False)
        with self.assertRaises(ValueError): jobs.begin_submit(self.s,app['id'])
        receipt=self.s.root/'evidence/history.txt'; receipt.parent.mkdir(); receipt.write_text('Fictional original receipt')
        row=jobs.outcome(Store(self.s.workspace),app['id'],{'attempt_id':attempt['id'],'result':'confirmed','detail':'Fictional history only','observed_confirmation':True,'confirmation_text':'Received','confirmation_url':'https://example.invalid/history','evidence_path':'evidence/history.txt','next_action':'Wait'})
        self.assertEqual('Submitted',row['status']); self.assertEqual(1,len(row['attempts']))
        self.assertTrue((self.s.root/row['attempts'][0]['resume_path']).is_file())

    def legacy_attempt(self):
        app,_,review=self.ready(); jobs.prepare(self.s,app['id'],review)
        tracker=self.s.read('tracker.json'); attempt=tracker['records'][0]['attempts'][0]
        attempt.update(id='legacy-attempt',resume_path='packages/demo-job/resume.pdf')
        for key in ['snapshot_path','snapshot_sha256','draft_resume_path']: attempt.pop(key,None)
        self.s.write('tracker.json',tracker)
        return app,attempt

    def test_legacy_unknown_pdf_is_preserved_before_render(self):
        app,attempt=self.legacy_attempt(); jobs.begin_submit(self.s,app['id'])
        before=(self.s.root/'packages/demo-job/resume.pdf').read_bytes()
        resume.render(self.s,'demo-job',draft(self.s),False)
        saved=self.s.read('tracker.json')['records'][0]['attempts'][0]
        self.assertNotEqual(attempt['resume_path'],saved['resume_path'])
        self.assertEqual(before,(self.s.root/saved['resume_path']).read_bytes())
        self.assertEqual('unknown',saved['outcome'])

    def test_legacy_submitted_pdf_is_preserved_before_render(self):
        app,attempt=self.legacy_attempt(); jobs.begin_submit(self.s,app['id'])
        receipt=self.s.root/'evidence/legacy.txt'; receipt.parent.mkdir(); receipt.write_text('Fictional legacy receipt')
        jobs.outcome(self.s,app['id'],{'attempt_id':attempt['id'],'result':'confirmed','detail':'Fictional mock only','observed_confirmation':True,'confirmation_text':'Received','confirmation_url':'https://example.invalid/thanks','evidence_path':'evidence/legacy.txt','next_action':'Wait'})
        resume.render(self.s,'demo-job',draft(self.s),False)
        row=self.s.read('tracker.json')['records'][0]
        self.assertEqual('Submitted',row['status'])
        self.assertEqual(attempt['pdf_sha256'],digest((self.s.root/row['attempts'][0]['resume_path']).read_bytes()))

    def test_missing_or_changed_legacy_pdf_blocks_before_package_changes(self):
        app,_=self.legacy_attempt(); jobs.begin_submit(self.s,app['id'])
        before=self.s.read('tracker.json')
        pdf=self.s.root/'packages/demo-job/resume.pdf'
        for mode in ['changed','missing']:
            if mode=='changed': pdf.write_bytes(b'Changed historical bytes')
            else: pdf.unlink()
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError,'original'): resume.render(self.s,'demo-job',draft(self.s),False)
            self.assertEqual(before,self.s.read('tracker.json'))
            self.assertFalse((self.s.root/'packages/demo-job/resume.tex').exists())

    def test_snapshot_write_failure_records_no_partial_attempt_and_can_retry(self):
        app,_,review=self.ready(); original=jobs.atomic_bytes
        def deny(path,data):
            if Path(path).name=='profile.json': raise PermissionError('Fictional denied snapshot write')
            return original(path,data)
        with patch.object(jobs,'atomic_bytes',deny), self.assertRaises(PermissionError): jobs.prepare(self.s,app['id'],review)
        self.assertEqual([],self.s.read('tracker.json')['records'][0]['attempts'])
        with self.assertRaises(ValueError): jobs.begin_submit(self.s,app['id'])
        jobs.prepare(self.s,app['id'],review); jobs.begin_submit(self.s,app['id'])

    def test_changed_snapshot_blocks_click_even_when_live_pdf_is_unchanged(self):
        app,_,review=self.ready(); attempt=jobs.prepare(self.s,app['id'],review)
        (self.s.root/attempt['resume_path']).write_bytes(b'Tampered snapshot')
        with self.assertRaisesRegex(ValueError,'Historical PDF'): jobs.begin_submit(self.s,app['id'])

    def test_unknown_click_cannot_be_repeated(self):
        a,g,r=self.ready();jobs.prepare(self.s,a['id'],r);jobs.begin_submit(self.s,a['id'])
        with self.assertRaises(ValueError):jobs.begin_submit(self.s,a['id'])
        with self.assertRaises(ValueError):jobs.prepare(self.s,a['id'],r)

    def test_confirm_requires_persisted_evidence(self):
        a,g,r=self.ready();jobs.prepare(self.s,a['id'],r);jobs.begin_submit(self.s,a['id'])
        attempt=self.s.read('tracker.json')['records'][0]['attempts'][-1]['id']
        with self.assertRaisesRegex(ValueError,'Persist confirmation'):jobs.outcome(self.s,a['id'],{'attempt_id':attempt,'result':'confirmed','detail':'test','observed_confirmation':True,'confirmation_text':'Application received','evidence_path':'evidence/missing.txt','confirmation_url':'https://example.invalid/thanks','next_action':'Wait'})

    def test_explicit_confirmation_is_recorded(self):
        a,g,r=self.ready();jobs.prepare(self.s,a['id'],r);jobs.begin_submit(self.s,a['id'])
        p=self.s.root/'evidence/receipt.txt';p.parent.mkdir();p.write_text('Observed fictional application received')
        attempt=self.s.read('tracker.json')['records'][0]['attempts'][-1]['id']
        row=jobs.outcome(self.s,a['id'],{'attempt_id':attempt,'result':'confirmed','detail':'Local mock only','observed_confirmation':True,'confirmation_text':'Application received','evidence_path':'evidence/receipt.txt','confirmation_url':'https://example.invalid/thanks','next_action':'Wait'})
        self.assertEqual('Submitted',row['status']);self.assertIn('pdf_sha256',row['attempts'][-1])
        self.assertEqual(1,self.s.read('tracker.json')['record_count'])

    def test_uncertain_failure_needs_non_submission_evidence(self):
        a,g,r=self.ready();jobs.prepare(self.s,a['id'],r);jobs.begin_submit(self.s,a['id'])
        attempt=self.s.read('tracker.json')['records'][0]['attempts'][-1]['id']
        with self.assertRaisesRegex(ValueError,'proof of non-submission'):jobs.outcome(self.s,a['id'],{'attempt_id':attempt,'result':'failed','detail':'Network timeout'})

    def test_preclick_handoff_requires_new_preparation(self):
        a,g,r=self.ready(); attempt=jobs.prepare(self.s,a['id'],r)
        jobs.outcome(self.s,a['id'],{'attempt_id':attempt['id'],'result':'needs-user','detail':'Required answer changed'})
        with self.assertRaises(ValueError):jobs.begin_submit(self.s,a['id'])
        new=jobs.prepare(self.s,a['id'],r)
        self.assertNotEqual(attempt['id'],new['id'])
        jobs.begin_submit(self.s,a['id'])

    def test_late_observation_cannot_change_new_attempt(self):
        a,g,r=self.ready(); old=jobs.prepare(self.s,a['id'],r)
        jobs.outcome(self.s,a['id'],{'attempt_id':old['id'],'result':'needs-user','detail':'Waiting for user'})
        jobs.prepare(self.s,a['id'],r);jobs.begin_submit(self.s,a['id'])
        with self.assertRaisesRegex(ValueError,'latest attempt_id'):
            jobs.outcome(self.s,a['id'],{'attempt_id':old['id'],'result':'failed','detail':'Late old page result','verified_not_submitted':True})
        self.assertEqual('unknown',self.s.read('tracker.json')['records'][0]['attempts'][-1]['outcome'])

    def test_unknown_outcome_requires_click_intent(self):
        a,g,r=self.ready();attempt=jobs.prepare(self.s,a['id'],r)
        with self.assertRaisesRegex(ValueError,'click intent'):
            jobs.outcome(self.s,a['id'],{'attempt_id':attempt['id'],'result':'unknown','detail':'No click yet'})

    def test_reopen_uncertain_attempt_and_reconcile(self):
        a,g,r=self.ready();jobs.prepare(self.s,a['id'],r);started=jobs.begin_submit(self.s,a['id'])
        reopened=Store(self.s.workspace); reopened.initialize()
        self.assertEqual(1,reopened.status()['applications']['counts']['Needs user'])
        with self.assertRaises(ValueError):jobs.prepare(reopened,a['id'],r)
        p=reopened.root/'evidence/receipt.txt';p.parent.mkdir();p.write_text('Fictional platform history confirms received')
        jobs.outcome(reopened,a['id'],{'attempt_id':started['attempt_id'],'result':'confirmed','detail':'Reconciled platform history','observed_confirmation':True,'confirmation_text':'Received','confirmation_url':'https://example.invalid/history','evidence_path':'evidence/receipt.txt','next_action':'Wait'})
        self.assertEqual(1,reopened.status()['applications']['counts']['Submitted'])

    def test_accounts_file_cannot_be_imported_as_resume(self):
        p=self.s.root/'credentials/workday/accounts.txt';p.parent.mkdir(parents=True);p.write_text('FICTIONAL ONLY: this must never be imported')
        before=self.s.read('sources.json')
        with self.assertRaisesRegex(ValueError,'not career sources'):profiles.import_source(self.s,p)
        self.assertEqual(before,self.s.read('sources.json'))

    def test_role_requires_valid_focus_and_local_sources(self):
        for patch in [{'focus':'not a list'}, {'jd_source_ids':['missing-source']}, {'jd_source_ids':'not a list'}, {'tailoring_guidance':'not a list'}]:
            with self.assertRaises(ValueError):
                profiles.role_create(self.s,{'id':'test','title':'Tester','focus':['Testing'],**patch},['codex'])
        self.assertFalse((self.s.root/'roles/test.json').exists())

    def test_generated_skill_reads_current_role_without_static_guides(self):
        role=self.s.read('roles/operations.json')
        route=self.s.root/role['route_path']
        self.assertEqual(digest(route.read_bytes()),role['route_sha256'])
        for host in ['.agents','.claude']:
            text=(self.s.workspace/host/'skills/career-resume-operations/SKILL.md').read_text()
            self.assertNotIn('references/routes/',text)
            self.assertIn('.career-assistant/roles/operations.json',text)
            self.assertIn('.career-assistant/routes/operations.md',text)
            self.assertIn('references/matching.md',text)
            self.assertNotIn('Riley Stone',text)

    def test_user_defined_direction_is_scorable_without_builtin_category(self):
        profiles.update_preferences(self.s,{'targets':[{'id':'heritage-preservation','title':'Museum Conservator'}]})
        role=profiles.role_create(self.s,{'id':'heritage-preservation','title':'Museum Conservator','focus':['Collection condition assessment'],'tailoring_guidance':['Request evidence for conservation methods and qualifications.']},['codex','claude'])
        self.assertTrue(role['provisional'])
        self.assertNotIn('route',role)
        a=assessment(self.s,'conservator-job')
        a['job'].update(role_id=role['id'],title=role['title'],text='FICTIONAL JD: Museum Conservator assesses collection condition, documents conservation methods and needs supported conservation qualifications. No candidate experience is assumed.')
        a['requirements']=[{'requirement':'Collection condition assessment','must_have':True,'match':'unknown','rationale':'No conservation facts in this fictional profile.'}]
        a['eligibility']=[{'criterion':'Required conservation qualifications','result':'unknown','reason':'Ask for evidence of the required qualification.'}]
        result=jobs.assess(self.s,a)
        self.assertEqual(0,result['fit_score'])
        self.assertEqual('unknown',result['eligibility_result'])

    def test_role_guidance_links_jd_and_refreshes_legacy_skill(self):
        before=self.s.read('profile.json')
        source=self.s.root/'fictional-jd.txt'
        source.write_text('FICTIONAL JD: plan capacity and coordinate service delivery.',encoding='utf-8')
        sid=profiles.import_source(self.s,source)['source_id']
        for host in ['.agents','.claude']:
            (self.s.workspace/host/'skills/career-resume-operations/SKILL.md').write_text('Legacy skill references/routes/pm-operations.md',encoding='utf-8')
        role=profiles.role_create(self.s,{'id':'operations','title':'Operations Manager','route':'pm-operations','focus':['Capacity planning'],'tailoring_guidance':['Use evidenced service outcomes.'],'jd_source_ids':[sid]},['codex','claude'])
        self.assertFalse(role['provisional'])
        self.assertEqual([sid],self.s.read('roles/operations.json')['jd_source_ids'])
        self.assertEqual(['Use evidenced service outcomes.'],role['tailoring_guidance'])
        self.assertEqual(before,self.s.read('profile.json'))
        self.assertIn('Use evidenced service outcomes.',(self.s.root/role['route_path']).read_text())
        for host in ['.agents','.claude']:
            text=(self.s.workspace/host/'skills/career-resume-operations/SKILL.md').read_text()
            self.assertNotIn('references/routes/',text)
            self.assertNotIn('Riley Stone',text)

    def test_no_route_before_user_selects_a_direction(self):
        s=Store(Path(self.temp.name)/'blank-user');s.initialize()
        self.assertFalse((s.root/'routes').exists())
        payload={'id':'logistics','title':'Logistics Coordinator','focus':['Shipment planning']}
        with self.assertRaisesRegex(ValueError,'choose this direction'):
            profiles.role_create(s,payload,['codex','claude'])
        self.assertFalse((s.root/'routes').exists())
        self.assertFalse((s.workspace/'.agents/skills/career-resume-logistics').exists())
        profiles.update_preferences(s,{'targets':['Logistics Coordinator'],'locations':['Fictional City'],'work_modes':['hybrid']})
        role=profiles.role_create(s,payload,['codex','claude'])
        self.assertTrue((s.root/role['route_path']).is_file())
        self.assertEqual(['logistics.md'],[p.name for p in (s.root/'routes').iterdir()])

    def test_personal_routes_stay_separate_across_users_and_reopens(self):
        b=make_workspace(Path(self.temp.name)/'different-user','software')
        path=self.s.root/'routes/operations.md';before=path.read_bytes()
        Store(self.s.workspace).initialize()
        self.assertEqual(before,path.read_bytes())
        self.assertFalse((self.s.root/'routes/software.md').exists())
        self.assertFalse((b.root/'routes/operations.md').exists())
        self.assertNotEqual(before,(b.root/'routes/software.md').read_bytes())

    def test_roles_checkpoint_requires_every_selected_personal_guide(self):
        for step in ['environment','materials','facts','preferences']:
            profiles.checkpoint(self.s,step)
        guide=self.s.root/'routes/operations.md'
        guide.unlink()
        with self.assertRaisesRegex(ValueError,'personal route'):
            profiles.checkpoint(self.s,'roles')
        profiles.role_create(self.s,{'id':'operations','title':'Operations Manager','focus':['Service execution']},['codex'])
        profiles.update_preferences(self.s,{'targets':['operations','logistics']})
        with self.assertRaisesRegex(ValueError,'personal route'):
            profiles.checkpoint(self.s,'roles')
        profiles.role_create(self.s,{'id':'logistics','title':'Logistics Coordinator','focus':['Shipment planning']},['codex'])
        profiles.checkpoint(self.s,'roles')

    def test_unselected_direction_cannot_create_a_route(self):
        before=list((self.s.root/'routes').iterdir())
        with self.assertRaisesRegex(ValueError,'choose this direction'):
            profiles.role_create(self.s,{'id':'unselected','title':'Unselected Job','focus':['Example']},['codex'])
        self.assertEqual(before,list((self.s.root/'routes').iterdir()))

    def test_installed_host_helpers_resume_and_render_same_workspace(self):
        root=Path(self.temp.name)/'fresh-cli-user'
        installer.install(root,user_root=Path(self.temp.name)/'isolated-home')
        host='.agents'
        def cli(*args,payload=None):
            args=list(args)
            if payload is not None:
                input_path=root/'.career-assistant/input.json'
                input_path.write_text(json.dumps(payload),encoding='utf-8')
                args += ['--input',str(input_path)]
            script=root/host/'skills/career-assistant/scripts/career.py'
            result=subprocess.run([sys.executable,str(script),'--workspace',str(root),*args],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(0,result.returncode,result.stderr)
            return json.loads(result.stdout)
        self.assertFalse((root/'.career-assistant').exists())
        cli('init');cli('checkpoint','environment')
        source=root/'.career-assistant/statement.txt'
        supplied=self.s.read('profile.json')['facts']
        source.write_text('FICTIONAL CLI TEST\n'+'\n'.join(f['text'] for f in supplied.values()),encoding='utf-8')
        sid=cli('import-source',str(source),'--kind','user-statement')['source_id']
        cli('checkpoint','materials')
        facts={fid:{**f,'source_ids':[sid]} for fid,f in supplied.items()}
        cli('profile-update',payload={'facts':facts});cli('checkpoint','facts')
        before=(root/'.career-assistant/profile.json').read_bytes()
        # New processes through the other host installation resume persisted state.
        host='.claude'
        self.assertEqual('preferences',cli('init')['next_step'])
        self.assertEqual(before,(root/'.career-assistant/profile.json').read_bytes())
        cli('preferences-update',payload={'targets':['operations'],'submission_policy':'per-application'})
        cli('checkpoint','preferences')
        cli('role-create',payload={'id':'operations','title':'Operations Manager','focus':['Service execution']})
        self.assertTrue((root/'.claude/skills/career-resume-operations/SKILL.md').is_file())
        self.assertFalse((root/'.agents/skills/career-resume-operations').exists())
        self.assertTrue((root/'.career-assistant/routes/operations.md').is_file())
        cli('checkpoint','roles');cli('checkpoint','automation')
        cli('assess',payload=assessment(self.s))
        cli('render','demo-job','--source-only',payload=draft(self.s))
        self.assertEqual('trial',cli('status')['next_step'])
        self.assertEqual([],json.loads((root/'.career-assistant/grants.json').read_text())['grants'])
        self.assertNotIn('\\section{Projects}',(root/'.career-assistant/packages/demo-job/resume.tex').read_text())

    def test_install_both_hashes_and_no_silent_replace(self):
        target=Path(self.temp.name)/'install';user=Path(self.temp.name)/'fake-user'
        result=installer.install(target,user_root=user)
        self.assertEqual(2,len(result['actions']))
        source_hashes=installer.inventory(installer.SOURCE)
        self.assertEqual(source_hashes,installer.inventory(target/'.claude/skills/career-assistant'))
        (target/'.agents/skills/career-assistant/SKILL.md').write_text('local changes')
        with self.assertRaises(ValueError):installer.install(target,user_root=user)
        installer.install(target,replace=True,user_root=user)
        self.assertTrue(list((target/'.career-assistant/skill-backups').rglob('SKILL.md')))

if __name__=='__main__':unittest.main()
