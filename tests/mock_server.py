"""Loopback-only fake application form; never proxies a real employer."""
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from email.parser import BytesParser
from email.policy import default

HTML='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Fictional application test</title>
<h1>Fictional Employer — Test role</h1><p>Local mock only. Not a real application.</p>
<form id="application"><label>Full name <input id="name" name="name" required></label>
<label>Resume <input id="resume" name="resume" type="file" accept=".pdf" required></label>
<button type="submit">Submit application</button></form><div id="result" role="status"></div>
<script>
const mode=new URLSearchParams(location.search).get('mode')||'success';
if(mode==='captcha') { document.querySelector('form').insertAdjacentHTML('beforeend','<p id="captcha">CAPTCHA: user action required</p>'); }
document.querySelector('form').onsubmit=async e=>{e.preventDefault();
 if(mode==='captcha')return;
 const r=await fetch('/submit?mode='+mode,{method:'POST',body:new FormData(e.target)});
 const data=await r.json();document.querySelector('#result').textContent=data.message;
 if(data.submitted)document.querySelector('button').disabled=true;
};</script></html>'''

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(HTML.encode())
    def do_POST(self):
        size=int(self.headers.get('Content-Length','0'))
        if size>5_000_000:self.send_error(413);return
        body=self.rfile.read(size)
        message=BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers['Content-Type']+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
        attachments=[p for p in message.iter_parts() if p.get_filename()] if message.is_multipart() else []
        mode=parse_qs(urlsplit(self.path).query).get('mode',['success'])[0]
        if not attachments:
            status,payload=400,{'message':'Required resume missing','submitted':False}
        elif mode=='failed':
            status,payload=409,{'message':'Application was not submitted: validation rejected','submitted':False}
        elif mode=='unknown':
            status,payload=202,{'message':'Request pending; outcome not known','submitted':False}
        else:
            status,payload=200,{'message':'Application received for Fictional Employer Test role','submitted':True,'attachment':attachments[0].get_filename()}
        self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(payload).encode())

if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}'}),flush=True)
    server.serve_forever()
