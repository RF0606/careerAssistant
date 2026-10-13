from __future__ import annotations
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from storage import SCHEMA, digest, now, slug, inside
from roles import context_hash

RUBRIC = '1.0'
STATUSES = {'Pending', 'Needs user', 'Blocked', 'Submitted'}

def canonical_url(url):
    u = urlsplit(url)
    if u.scheme not in {'https', 'http'} or not u.hostname or u.username or u.password:
        raise ValueError('Expected a public job URL without embedded credentials')
    params = [(k, v) for k, v in parse_qsl(u.query) if not k.lower().startswith(('utm_', 'trk')) and k.lower() not in {'source', 'ref', 'refid'}]
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path.rstrip('/'), urlencode(sorted(params)), ''))

def assess(store, payload):
    job = payload['job']
    slug(job['id'])
    if job.get('full_jd') is not True or len(job.get('text', '').strip()) < 80:
        raise ValueError('Full JD required; no numerical score from an incomplete posting')
    for key in ['company', 'title', 'role_id', 'captured_at']:
        if not job.get(key):
            raise ValueError(f'Missing job field: {key}')
    role_hash = context_hash(store, job['role_id'])
    job['url'] = canonical_url(job['url'])
    profile = store.read('profile.json')
    prefs = store.read('preferences.json')
    requirements = payload.get('requirements', [])
    if not requirements:
        raise ValueError('Record the JD requirements and evidence mapping first')
    total = earned = unknown_weight = 0
    gaps = []
    for row in requirements:
        match = row.get('match')
        if match not in {'direct', 'transferable', 'none', 'unknown'} or not row.get('requirement'):
            raise ValueError('Requirement needs text and direct/transferable/none/unknown match')
        weight = 3 if row.get('must_have') else 1
        if match in {'direct', 'transferable'}:
            ids = row.get('evidence_ids', [])
            if not ids or any(fid not in profile['facts'] or profile['facts'][fid]['status'] not in {'documented', 'user_confirmed'} for fid in ids):
                raise ValueError('Positive match requires documented or confirmed fact IDs')
        if not row.get('rationale'):
            raise ValueError('Every requirement needs a rationale')
        total += weight
        earned += weight * {'direct': 1, 'transferable': .5, 'none': 0, 'unknown': 0}[match]
        unknown_weight += weight if match == 'unknown' else 0
        if match in {'none', 'unknown'}:
            gaps.append(row['requirement'])
    eligibility = payload.get('eligibility', [])
    preferences = payload.get('preference_matches', [])
    for row in eligibility + preferences:
        if row.get('result') not in {'yes', 'no', 'unknown'} or not row.get('reason') or not row.get('criterion'):
            raise ValueError('Eligibility/preferences need criterion, result and reason')
    # Absence of assessed eligibility is unknown, never an implicit pass.
    gate = 'ineligible' if any(x['result'] == 'no' for x in eligibility) else 'unknown' if not eligibility or any(x['result'] == 'unknown' for x in eligibility) else 'eligible'
    known = [x for x in preferences if x['result'] != 'unknown']
    result = {'schema_version': SCHEMA, 'rubric_version': RUBRIC, 'job': job, 'requirements': requirements, 'eligibility': eligibility, 'eligibility_result': gate, 'preference_matches': preferences, 'fit_score': round(100 * earned / total), 'unknown_requirement_weight': unknown_weight, 'preference_score': round(100 * sum(x['result'] == 'yes' for x in known) / len(known)) if known else None, 'unknown_preferences': sum(x['result'] == 'unknown' for x in preferences), 'gaps': gaps, 'profile_hash': digest(profile), 'preferences_hash': digest(prefs), 'role_context_hash': role_hash, 'assessed_at': now()}
    with store.lock():
        store.write(f"jobs/{job['id']}.json", result)
    return result

def fresh(store, assessment):
    if assessment['profile_hash'] != digest(store.read('profile.json')) or assessment['preferences_hash'] != digest(store.read('preferences.json')):
        raise ValueError('Profile/preferences changed; refresh assessment and resume before continuing')
    if assessment.get('role_context_hash') != context_hash(store, assessment['job']['role_id']):
        raise ValueError('Role configuration/personal route changed or assessment predates context tracking; refresh assessment and resume before continuing')

def trial_ready(store):
    for path in (store.root / 'packages').glob('*/validation.json'):
        try:
            review = store.read(f'packages/{path.parent.name}/validation.json')
            assessment = store.read(f'jobs/{path.parent.name}.json')
            fresh(store, assessment)
            pdf = path.parent / 'resume.pdf'
            if review.get('status') == 'ready' and review.get('profile_hash') == assessment['profile_hash'] and review.get('assessment_hash') == digest(assessment) and review.get('pdf_sha256') == digest(pdf.read_bytes()):
                return True
        except (ValueError, KeyError, OSError):
            continue
    return False

def add_application(store, job_id):
    assessment = store.read(f'jobs/{slug(job_id)}.json')
    fresh(store, assessment)
    job = assessment['job']
    with store.lock():
        tracker = store.read('tracker.json')
        for row in tracker['records']:
            same_url = row['url'] == job['url']
            same_employer = row['company'].casefold() == job['company'].casefold()
            same_req = bool(job.get('requisition_id')) and row.get('requisition_id') == job.get('requisition_id')
            same_title = row['title'].casefold() == job['title'].casefold()
            if same_url or (same_employer and (same_req or same_title)):
                raise ValueError(f'Possible duplicate: {row["id"]}; review the existing record, including reposts')
        if assessment['eligibility_result'] == 'ineligible':
            raise ValueError('Confirmed eligibility failure: do not create an application')
        row = {'id': 'app-' + uuid.uuid4().hex[:12], 'job_id': job_id, 'company': job['company'], 'title': job['title'], 'url': job['url'], 'requisition_id': job.get('requisition_id'), 'status': 'Pending' if assessment['eligibility_result'] == 'eligible' else 'Needs user', 'attempts': [], 'created_at': now(), 'next_action': 'Review application materials and required answers'}
        tracker['records'].append(row)
        tracker['record_count'] = len(tracker['records'])
        store.write('tracker.json', tracker)
    return row

def grant(store, payload):
    policy = store.read('preferences.json')['submission_policy']
    jobs = payload.get('job_ids', [])
    count = payload.get('max_submissions')
    if policy is None or not payload.get('user_request') or not jobs:
        raise ValueError('Choose policy and record the actual user request plus concrete job IDs')
    if type(count) is not int or count < 1 or (policy == 'per-application' and (len(jobs) != 1 or count != 1)):
        raise ValueError('Invalid authorization count or per-application scope')
    for jid in jobs:
        store.read(f'jobs/{slug(jid)}.json')
    row = {'id': 'grant-' + uuid.uuid4().hex[:12], 'policy': policy, 'job_ids': jobs, 'max_submissions': count, 'user_request': payload['user_request'], 'created_at': now(), 'expires_at': (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(), 'used_application_ids': []}
    with store.lock():
        data = store.read('grants.json')
        data['grants'].append(row)
        store.write('grants.json', data)
    return row

def find_record(tracker, app_id):
    for row in tracker['records']:
        if row['id'] == app_id:
            return row
    raise ValueError('Application not found')

def verify_grant(store, grant_id, row):
    grants = store.read('grants.json')
    g = next((x for x in grants['grants'] if x['id'] == grant_id), None)
    if not g or datetime.fromisoformat(g['expires_at']) <= datetime.now(timezone.utc) or row['job_id'] not in g['job_ids']:
        raise ValueError('No current authorization for this job')
    if g['policy'] != store.read('preferences.json')['submission_policy']:
        raise ValueError('Submission policy changed; ask for a new grant')
    # Count click intents, including unknown outcomes, from the single atomic tracker.
    used = {r['id'] for r in store.read('tracker.json')['records'] if any(a.get('grant_id') == grant_id and a.get('started_at') for a in r['attempts'])}
    if row['id'] not in used and len(used) >= g['max_submissions']:
        raise ValueError('Authorization count exhausted')
    return g

def prepare(store, app_id, payload):
    with store.lock():
        tracker = store.read('tracker.json')
        row = find_record(tracker, app_id)
        if row['status'] == 'Submitted' or any(a.get('outcome') == 'unknown' for a in row['attempts']):
            raise ValueError('Already submitted or uncertain previous outcome; reconcile before another attempt')
        assessment = store.read(f"jobs/{row['job_id']}.json")
        fresh(store, assessment)
        if assessment['eligibility_result'] != 'eligible':
            raise ValueError('Resolve eligibility before applying')
        g = verify_grant(store, payload['grant_id'], row)
        package = store.root / 'packages' / row['job_id']
        review = store.read(f"packages/{row['job_id']}/validation.json")
        pdf = package / 'resume.pdf'
        if review.get('status') != 'ready' or review.get('pdf_sha256') != digest(pdf.read_bytes()) or review.get('profile_hash') != assessment['profile_hash'] or review.get('assessment_hash') != digest(assessment):
            raise ValueError('Resume validation is missing, changed, or stale')
        if payload.get('unresolved_fields') != [] or payload.get('all_required_fields_reviewed') is not True or not payload.get('review_evidence'):
            raise ValueError('Review every required field; unresolved answers require user action')
        profile = store.read('profile.json')
        for answer in payload.get('answers', []):
            refs = answer.get('fact_ids', [])
            if not refs or any(f not in profile['facts'] or profile['facts'][f]['status'] not in {'documented', 'user_confirmed'} for f in refs):
                raise ValueError('Answers require usable fact IDs')
            if answer.get('high_impact') and any(profile['facts'][f]['status'] != 'user_confirmed' for f in refs):
                raise ValueError('High-impact answers require explicit user-confirmed facts')
        attempt = {'id': uuid.uuid4().hex, 'grant_id': g['id'], 'prepared_at': now(), 'profile_hash': assessment['profile_hash'], 'assessment_hash': digest(assessment), 'pdf_sha256': review['pdf_sha256'], 'resume_path': f"packages/{row['job_id']}/resume.pdf", 'answers': payload.get('answers', []), 'review_evidence': payload['review_evidence'], 'outcome': 'prepared'}
        row['attempts'].append(attempt)
        row['status'] = 'Pending'
        store.write('tracker.json', tracker)
    return attempt

def begin_submit(store, app_id):
    with store.lock():
        tracker = store.read('tracker.json')
        row = find_record(tracker, app_id)
        if row['status'] != 'Pending' or not row['attempts'] or row['attempts'][-1]['outcome'] != 'prepared':
            raise ValueError('No unused submission preparation')
        attempt = row['attempts'][-1]
        assessment = store.read(f"jobs/{row['job_id']}.json")
        fresh(store, assessment)
        verify_grant(store, attempt['grant_id'], row)
        if attempt['assessment_hash'] != digest(assessment) or attempt['pdf_sha256'] != digest((store.root / attempt['resume_path']).read_bytes()):
            raise ValueError('Prepared inputs changed')
        attempt['started_at'] = now()
        attempt['outcome'] = 'unknown'
        row['status'] = 'Needs user'
        row['next_action'] = 'Await observed submission confirmation; never retry an uncertain click'
        store.write('tracker.json', tracker)
    return {'application_id': app_id, 'attempt_id': attempt['id'], 'action': 'User-authorized final submit may now be clicked ONCE. Record observed outcome immediately.'}

def outcome(store, app_id, payload):
    result = payload.get('result')
    if result not in {'confirmed', 'failed', 'unknown', 'needs-user'}:
        raise ValueError('Invalid outcome')
    with store.lock():
        tracker = store.read('tracker.json')
        row = find_record(tracker, app_id)
        if row['status'] == 'Submitted':
            raise ValueError('Submitted record is immutable through this command')
        if not payload.get('detail'):
            raise ValueError('Outcome requires an observation/detail')
        attempt = row['attempts'][-1] if row['attempts'] else None
        if attempt and payload.get('attempt_id') != attempt['id']:
            raise ValueError('Outcome must identify the latest attempt_id; reject stale browser observations')
        if result == 'unknown' and (not attempt or not attempt.get('started_at')):
            raise ValueError('Unknown submission requires a persisted click intent; use needs-user before clicking')
        if result == 'confirmed':
            if not attempt or attempt['outcome'] != 'unknown':
                raise ValueError('Only an attempted submission can be confirmed')
            if payload.get('observed_confirmation') is not True or not payload.get('confirmation_text'):
                raise ValueError('Explicit observed confirmation required')
            evidence = inside(store.root, store.root / payload['evidence_path'])
            if not evidence.is_file() or evidence.stat().st_size == 0:
                raise ValueError('Persist confirmation evidence before closing the page')
            if not payload.get('confirmation_url') or not payload.get('next_action'):
                raise ValueError('Confirmation URL and next action are required')
            attempt.update({'outcome': 'confirmed', 'evidence_path': evidence.relative_to(store.root).as_posix(), 'evidence_sha256': digest(evidence.read_bytes()), 'confirmation_text': payload['confirmation_text'], 'confirmation_url': payload['confirmation_url'], 'confirmed_at': now()})
            row['status'] = 'Submitted'
        elif result == 'failed':
            if attempt and attempt['outcome'] == 'unknown' and payload.get('verified_not_submitted') is not True:
                raise ValueError('Uncertain clicks require proof of non-submission before retry')
            if attempt:
                attempt['outcome'] = 'failed'
            row['status'] = 'Blocked'
        else:
            if attempt and attempt['outcome'] == 'prepared':
                attempt['outcome'] = 'paused'
            row['status'] = 'Needs user'
        row['next_action'] = payload.get('next_action', payload['detail'])
        row['last_observation'] = {'at': now(), **payload}
        store.write('tracker.json', tracker)
    return row
