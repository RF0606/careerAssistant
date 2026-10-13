"""Prepare a new, explicitly fictional workspace for supervised host-browser QA."""
import argparse
import json
from pathlib import Path
import secrets
import uuid
from fixtures import make_workspace, assessment, draft
from storage import digest
import jobs
import resume


def prepare(results):
    workspace = Path(results).resolve() / ('host-browser-' + uuid.uuid4().hex[:12])
    store = make_workspace(workspace)
    credentials = store.root / 'credentials/workday/accounts.txt'
    credentials.parent.mkdir(parents=True)
    # Random test-only values stay in memory/local ignored files, never stdout.
    credentials.write_text('username: ' + 'fixture@example.invalid, password: ' + secrets.token_urlsafe(32) + '\n', encoding='utf-8')
    cases = {}
    for mode in ['success', 'unknown']:
        jid = 'host-' + mode
        jobs.assess(store, assessment(store, jid, 'Fictional ' + mode.title() + ' Employer'))
        result = resume.render(store, jid, draft(store))
        application = jobs.add_application(store, jid)
        cases[jid] = {'mode': mode, 'application_id': application['id'],
                      'pdf_path': str(store.root / f'packages/{jid}/resume.pdf'),
                      'preview_path': str(store.root / f'packages/{jid}/preview-1.png'),
                      'pdf_sha256': result['pdf_sha256'], 'company': application['company'], 'title': application['title']}
    fixture = {'fictional_test': True, 'cases': cases, 'profile_sha256': digest(store.read('profile.json'))}
    (store.root / 'host-browser-fixture.json').write_text(json.dumps(fixture, indent=2), encoding='utf-8')
    return {'workspace': str(workspace), 'cases': cases,
            'next_action': 'Open every actual PDF preview and check text before recording visual-review. Inspect the host form before grants/preparation. Never use this fixture in a real profile or application.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path(__file__).resolve().parents[1] / 'test-results/host-browser')
    print(json.dumps(prepare(parser.parse_args().results), indent=2))
