"""Entirely fictional data, also used for repeatable PDF demonstrations."""
from __future__ import annotations
import copy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills'/'career-assistant'/'scripts'))
from storage import Store, SCHEMA, digest, atomic
import profiles, jobs

def make_workspace(path, persona='operations'):
    store=Store(path); store.initialize()
    developer=persona=='software'
    values={
        'name':'Morgan Reed' if developer else 'Riley Stone',
        'contact':'morgan@example.invalid | Manchester, UK' if developer else 'riley@example.invalid | Boston, MA',
        'headline':'Software Engineer' if developer else 'Operations Manager',
        'summary':'Software engineer delivering TypeScript services, tests and reliable releases.' if developer else 'Operations manager improving service quality, capacity planning and cross-team execution.',
        'skills':'TypeScript, APIs, automated testing' if developer else 'Capacity planning, stakeholder communication, process improvement',
        'employer':'Fictional Harbor Software' if developer else 'Fictional Cedar Services',
        'dates':'Jan 2023 - Dec 2025',
        'title':'Software Developer' if developer else 'Operations Supervisor',
        'location':'Manchester, UK' if developer else 'Boston, MA',
        'bullet':'Built TypeScript APIs with automated tests and monitored releases.' if developer else 'Coordinated a 12-person service team and improved response times by 20%.',
        'school':'Fictional North College',
        'degree':'BSc, Computer Science' if developer else 'BA, Business Administration',
        'school-dates':'2018 - 2022',
        'authorization':'Authorized to work in the UK' if developer else 'Authorized to work in the United States',
        'project-name':'Fictional Community Scheduler',
        'project-title':'Volunteer Developer',
        'project-dates':'2025',
        'project-bullet':'Built a scheduling tool for a volunteer group.',
        'special':'R&D coordination, C#, 12% improvement and data_quality checks',
    }
    statement=store.root/'fixture-statement.txt'; statement.write_text('FICTIONAL TEST PERSON.\n'+'\n'.join(values.values()),encoding='utf-8')
    sid=profiles.import_source(store,statement,'user-statement')['source_id']
    profiles.update_profile(store,{'facts':{k:{'text':v,'category':'fixture','status':'user_confirmed','source_ids':[sid],'confirmation':'Fictional fixture confirms this test statement.'} for k,v in values.items()}})
    profiles.update_preferences(store,{'targets':[{'id':persona,'title':values['headline'],'priority':1}],'locations':[values['location']],'submission_policy':'per-batch'})
    profiles.role_create(store,{'id':persona,'title':values['headline'],'focus':['Test-backed engineering' if developer else 'Service execution'],'tailoring_guidance':['Select evidence for the fictional target and actual JD requirements.']},['codex','claude'])
    return store

def assessment(store,jid='demo-job',company='Fictional Employer',persona='operations'):
    term='TypeScript' if persona=='software' else 'capacity planning'
    return {'job':{'id':jid,'company':company,'title':'Software Engineer' if persona=='software' else 'Operations Manager','role_id':persona,'url':f'https://example.invalid/jobs/{jid}','requisition_id':jid,'captured_at':'2026-01-01T00:00:00Z','full_jd':True,'text':f'FICTIONAL JD FOR TESTING ONLY. The role requires {term}, clear communication, relevant qualifications and the right to work in the advertised location. This is not a live job.'},'requirements':[{'requirement':term,'must_have':True,'match':'direct','evidence_ids':['skills'],'rationale':'Fictional source records the required skill.','keywords':[term]}],'eligibility':[{'criterion':'Work authorization','result':'yes','reason':'Fictional confirmed authorization matches this test posting.'}],'preference_matches':[{'criterion':'Location','result':'yes','reason':'Test location matches.'}]}

def claim(store,key):
    return {'text':store.read('profile.json')['facts'][key]['text'],'evidence_ids':[key]}

def draft(store,with_projects=False):
    c=lambda k:claim(store,k)
    entry={'organization':c('employer'),'dates':c('dates'),'title':c('title'),'location':c('location'),'bullets':[c('bullet')]}
    d={'evidence_review':'Fictional demonstration: all claims map exactly to fixture statements.','header':{'name':c('name'),'headline':c('headline'),'contacts':[c('contact')]},'summary':c('summary'),'skills':[{'label':'Core skills','items':[c('skills')]}],'experience':[entry],'education':[{'organization':c('school'),'dates':c('school-dates'),'title':c('degree')}]}
    if with_projects:
        d.update({'include_projects':True,'project_section_request':'Fictional test user explicitly asks to show a Projects block.','projects':[{'organization':c('project-name'),'dates':c('project-dates'),'title':c('project-title'),'bullets':[c('project-bullet')]}]})
    return d

def stub_ready_package(store,jid='demo-job'):
    """A unit-test stub for tracker guards, not PDF generation acceptance evidence."""
    a=store.read(f'jobs/{jid}.json'); p=store.root/'packages'/jid; p.mkdir(parents=True,exist_ok=True)
    pdf=b'UNIT TEST PDF STUB - NOT A VERIFIED RESUME'
    (p/'resume.pdf').write_bytes(pdf)
    store.write(f'packages/{jid}/validation.json',{'schema_version':SCHEMA,'status':'ready','pdf_sha256':digest(pdf),'profile_hash':a['profile_hash'],'assessment_hash':digest(a)})

def authorized_preparation(store,jid='demo-job'):
    a=jobs.add_application(store,jid)
    g=jobs.grant(store,{'job_ids':[jid],'max_submissions':1,'user_request':'Fictional test user authorizes this one test job.'})
    review={'grant_id':g['id'],'all_required_fields_reviewed':True,'unresolved_fields':[],'review_evidence':'Unit fixture form reviewed','answers':[{'field':'Work authorization','value':'yes','fact_ids':['authorization'],'high_impact':True}]}
    return a,g,review

if __name__=='__main__':
    import argparse,json
    ap=argparse.ArgumentParser(); ap.add_argument('workspace',type=Path); ap.add_argument('--persona',choices=['operations','software'],default='operations'); ap.add_argument('--projects',action='store_true'); ap.add_argument('--compile',action='store_true'); args=ap.parse_args()
    s=make_workspace(args.workspace,args.persona); a=jobs.assess(s,assessment(s,persona=args.persona)); d=draft(s,args.projects)
    atomic(s.root/'demo-draft.json',d)
    atomic(s.root/'demo-assessment.json',assessment(s,persona=args.persona))
    if args.compile:
        import resume
        print(json.dumps(resume.render(s,'demo-job',d),indent=2))
    else:print(json.dumps({'workspace':str(s.workspace),'draft':'demo-draft.json','persona':args.persona},indent=2))
