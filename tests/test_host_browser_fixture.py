"""Backend guard tests use labelled byte stubs, not PDF acceptance evidence."""
import hashlib
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from host_browser_server import Handler


class HostFixtureTests(unittest.TestCase):
    def setUp(self):
        self.pdf = b'%PDF-1.7\nFICTIONAL BACKEND GUARD STUB - NOT A VERIFIED RESUME'
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.fixture = {'cases': {jid: {'company': 'Fictional Employer', 'title': 'Test role', 'mode': mode,
            'pdf_sha256': hashlib.sha256(self.pdf).hexdigest()} for jid, mode in [('host-success', 'success'), ('host-unknown', 'unknown')]}}
        self.server.pair = ('fixture@example.invalid', 'FICTIONAL-test-only')
        self.server.sessions, self.server.receipts, self.server.submit_counts, self.server.login_count = set(), {}, {}, 0
        self.snapshots = []
        self.server.persist = lambda: self.snapshots.append(json.loads(json.dumps({'login_count': self.server.login_count, 'submit_counts': self.server.submit_counts, 'receipts': self.server.receipts})))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.cookie = None
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, body=None, content_type=None):
        headers = {'Content-Type': content_type} if content_type else {}
        if self.cookie:
            headers['Cookie'] = self.cookie
        try:
            response = urlopen(Request(self.origin + path, data=body, headers=headers), timeout=5)
        except HTTPError as exc:
            response = exc
        return response.status, response.headers, response.read()

    def login(self):
        body = urlencode({'email': self.server.pair[0], 'secret': self.server.pair[1]}).encode()
        status, headers, _ = self.request('/login', body, 'application/x-www-form-urlencoded')
        self.assertEqual(200, status)
        self.cookie = headers['Set-Cookie'].split(';', 1)[0]

    def upload(self, jid, pdf=None):
        boundary = 'FICTIONAL-boundary'
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="name"\r\n\r\nFictional Candidate\r\n--{boundary}\r\nContent-Disposition: form-data; name="resume"; filename="resume.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
                + (self.pdf if pdf is None else pdf) + f'\r\n--{boundary}--\r\n'.encode())
        return self.request('/submit?job_id=' + jid, body, 'multipart/form-data; boundary=' + boundary)

    def test_login_and_exact_uploaded_hash_are_required_before_receipt(self):
        self.assertEqual(401, self.upload('host-success')[0])
        self.login()
        self.assertEqual(1, self.snapshots[-1]['login_count'])
        self.assertEqual(400, self.upload('host-success', b'%PDF-FICTIONAL WRONG FILE')[0])
        self.assertEqual({}, self.server.receipts)
        self.assertEqual(200, self.upload('host-success')[0])
        self.assertEqual({'host-success': 1}, self.server.submit_counts)

    def test_unknown_response_has_original_history_and_reauthentication_is_persisted(self):
        self.login()
        status, _, payload = self.upload('host-unknown')
        self.assertEqual(202, status)
        self.assertFalse(json.loads(payload)['submitted'])
        receipt = self.server.receipts['host-unknown'].copy()
        self.cookie = None
        self.login()
        self.assertEqual(2, self.snapshots[-1]['login_count'])
        status, _, page = self.request('/history')
        self.assertEqual(200, status)
        self.assertIn(receipt['receipt_id'].encode(), page)
        self.assertIn(receipt['resume_sha256'].encode(), page)
        self.assertEqual({'host-unknown': 1}, self.server.submit_counts)


if __name__ == '__main__':
    unittest.main()
