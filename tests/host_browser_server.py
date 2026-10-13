"""Loopback-only fictional login/upload/history for supervised Codex browser QA."""
import argparse
import hashlib
import html
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
from urllib.parse import parse_qs, urlsplit
from email.parser import BytesParser
from email.policy import default

STYLE = '<style>body{font:16px system-ui;margin:32px;max-width:900px}label{display:block;margin:16px 0}input,button{font:inherit;padding:8px}code{overflow-wrap:anywhere}article{border-top:1px solid #bbb;padding:16px 0}</style>'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, content, status=200, cookie=None):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        if cookie:
            self.send_header('Set-Cookie', 'fictional_session=' + cookie + '; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
        self.wfile.write(content.encode())

    def json(self, data, status=200, cookie=None):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        if cookie:
            self.send_header('Set-Cookie', 'fictional_session=' + cookie + '; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def authenticated(self):
        cookies = SimpleCookie(self.headers.get('Cookie', ''))
        return cookies.get('fictional_session') and cookies['fictional_session'].value in self.server.sessions

    def page(self, content):
        return '<!doctype html><html lang="en"><meta charset="utf-8"><title>Fictional host-browser acceptance</title>' + STYLE + '<h1>Fictional Workday test</h1><p>Local mock only. No real account or application.</p>' + content + '</html>'

    def do_GET(self):
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        if url.path == '/login' or not self.authenticated():
            captcha = '<p id="captcha">CAPTCHA: user action required. Do not continue login.</p>' if query.get('mode') == ['captcha'] else ''
            self.send(self.page('<form id="login"><label>Email <input id="email" type="email" name="email" required></label><label>Password <input id="secret" type="password" name="secret" required></label>' + captcha + '<button>Sign in</button></form><p id="result" role="status"></p><script>document.querySelector("form").onsubmit=async e=>{e.preventDefault();if(document.querySelector("#captcha"))return;let r=await fetch("/login",{method:"POST",body:new URLSearchParams(new FormData(e.target))});let d=await r.json();if(d.authenticated)location.href="/apply?job_id=host-success";else document.querySelector("#result").textContent=d.message;};</script>'))
            return
        if url.path == '/history':
            cards = ''.join('<article data-job-id="' + html.escape(jid) + '"><h2>' + html.escape(self.server.fixture['cases'][jid]['company']) + '</h2><p>Application received</p><p>Job ID: ' + jid + '</p><p>Receipt: ' + record['receipt_id'] + '</p><p>Uploaded resume: resume.pdf</p><p>SHA-256: <code>' + record['resume_sha256'] + '</code></p></article>' for jid, record in self.server.receipts.items())
            self.send(self.page('<h2>Candidate Home / Application history</h2>' + (cards or '<p>No applications yet.</p>')))
            return
        jid = query.get('job_id', ['host-success'])[0]
        case = self.server.fixture['cases'].get(jid)
        if not case:
            self.send(self.page('<p>Unknown fictional job.</p>'), 404)
            return
        self.send(self.page('<h2>' + html.escape(case['company']) + ' — ' + html.escape(case['title']) + '</h2><p>Job ID: ' + jid + '</p><a href="/history">Candidate Home / Application history</a><form id="application"><label>Full name <input id="name" name="name" required></label><label>Resume <input id="resume" name="resume" type="file" accept=".pdf" required></label><button>Submit application</button></form><div id="result" role="status"></div><script>document.querySelector("form").onsubmit=async e=>{e.preventDefault();let r=await fetch("/submit?job_id=' + jid + '",{method:"POST",body:new FormData(e.target)});let d=await r.json();document.querySelector("#result").textContent=d.message;if(d.submitted)document.querySelector("button").disabled=true;};</script>'))

    def do_POST(self):
        size = int(self.headers.get('Content-Length', '0'))
        if size > 5_000_000:
            self.json({'message': 'Request too large'}, 413)
            return
        body = self.rfile.read(size)
        url = urlsplit(self.path)
        if url.path == '/login':
            fields = parse_qs(body.decode())
            if (fields.get('email', [''])[0], fields.get('secret', [''])[0]) != self.server.pair:
                self.json({'authenticated': False, 'message': 'Invalid credentials'}, 401)
                return
            session = secrets.token_urlsafe(24)
            self.server.sessions.add(session)
            self.server.login_count += 1
            self.server.persist()
            self.json({'authenticated': True}, cookie=session)
            return
        if url.path != '/submit' or not self.authenticated():
            self.json({'submitted': False, 'message': 'Not authenticated'}, 401)
            return
        jid = parse_qs(url.query).get('job_id', [''])[0]
        case = self.server.fixture['cases'].get(jid)
        message = BytesParser(policy=default).parsebytes(('Content-Type: ' + self.headers.get('Content-Type', '') + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + body)
        attachments = [part for part in message.iter_parts() if part.get_filename()] if message.is_multipart() else []
        names = [part.get_payload(decode=True).decode('utf-8', errors='replace').strip() for part in message.iter_parts() if part.get_param('name', header='Content-Disposition') == 'name'] if message.is_multipart() else []
        if not case or len(attachments) != 1 or len(names) != 1 or not names[0]:
            self.json({'submitted': False, 'message': 'Required fictional resume missing'}, 400)
            return
        pdf = attachments[0].get_payload(decode=True)
        fingerprint = hashlib.sha256(pdf).hexdigest()
        if not pdf.startswith(b'%PDF-') or fingerprint != case['pdf_sha256']:
            self.json({'submitted': False, 'message': 'Wrong resume; application not submitted'}, 400)
            return
        self.server.submit_counts[jid] = self.server.submit_counts.get(jid, 0) + 1
        self.server.receipts.setdefault(jid, {'receipt_id': 'mock-' + secrets.token_hex(6), 'resume_sha256': fingerprint})
        self.server.persist()
        if case['mode'] == 'unknown':
            self.json({'submitted': False, 'message': 'Request pending; outcome not known. Check Candidate Home.'}, 202)
        else:
            self.json({'submitted': True, 'message': 'Application received for ' + case['company'] + '. Resume SHA-256: ' + fingerprint})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    workspace = parser.parse_args().workspace.resolve()
    fixture = json.loads((workspace / '.career-assistant/host-browser-fixture.json').read_text(encoding='utf-8'))
    if fixture.get('fictional_test') is not True or not workspace.name.startswith('host-browser-'):
        raise SystemExit('Use a newly generated fictional host-browser fixture only')
    # Exact random fixture pair is read in memory for mock authentication, never logged.
    text = (workspace / '.career-assistant/credentials/workday/accounts.txt').read_text(encoding='utf-8')
    match = re.fullmatch(r'username: (fixture@example\.invalid), password: ([A-Za-z0-9_-]+)\n', text)
    if not match:
        raise SystemExit('Invalid fictional credential fixture; values omitted')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.fixture, server.pair = fixture, match.groups()
    server.sessions, server.receipts, server.submit_counts, server.login_count = set(), {}, {}, 0
    state_path = workspace / '.career-assistant/mock-observations.json'
    def persist():
        state_path.write_text(json.dumps({'login_count': server.login_count, 'submit_counts': server.submit_counts, 'receipts': server.receipts}, indent=2), encoding='utf-8')
    server.persist = persist
    print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}/login', 'origin': f'http://127.0.0.1:{server.server_port}'}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
