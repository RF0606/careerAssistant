import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn, execFileSync } from 'node:child_process';
import { chromium } from 'playwright';
import { parseCredentials, fillWorkday, createWorkdayLoginSession } from '../skills/career-assistant/scripts/local_credentials.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const python=process.env.CAREER_TEST_PYTHON||'python';
const dir=await mkdtemp(path.join(os.tmpdir(),'career-browser-'));
const server=spawn(python,[path.join(root,'tests/mock_server.py')],{stdio:['ignore','pipe','pipe'],windowsHide:true});
let browser;
const passed=[];
const run=(args)=>JSON.parse(execFileSync(python,args,{cwd:root,encoding:'utf8',windowsHide:true,stdio:['ignore','pipe','pipe']}));
const command=(workspace,...args)=>run([path.join(root,'skills/career-assistant/scripts/career.py'),'--workspace',workspace,...args]);
try {
 const url=await new Promise((resolve,reject)=>{
  let text=''; const timer=setTimeout(()=>reject(new Error('Mock server startup timeout')),10000);
  server.stdout.on('data',d=>{text+=d;if(text.includes('\n')){clearTimeout(timer);resolve(JSON.parse(text.split('\n')[0]).url);}});
  server.on('error',reject);server.on('exit',code=>{if(code)reject(new Error('Mock server exited'));});
 });
 browser=await chromium.launch({headless:true});
 for(const mode of ['success','missing','captcha','failed','unknown']) {
  const workspace=path.join(dir,mode);
  const setup=run([path.join(root,'tests/browser_bridge.py'),workspace,mode]);
  const page=await browser.newPage(); await page.goto(url+'/?mode='+mode);
  await page.locator('#resume').setInputFiles(setup.pdf_path);
  assert.equal(await page.locator('#resume').evaluate(el=>el.files[0].name),'resume.pdf');
  if(mode!=='missing')await page.locator('#name').fill('Fictional candidate');
  let observation;
  let attemptId;
  if(mode==='missing') {
   assert.equal(await page.locator('#name').evaluate(el=>el.validity.valueMissing),true);
   assert.equal(await page.locator('#result').textContent(),'');
   observation={result:'needs-user',detail:'Required name missing; no final click authorized'};
  } else if(mode==='captcha') {
   assert.match(await page.locator('#captcha').textContent(),/CAPTCHA/);
   observation={result:'needs-user',detail:'CAPTCHA requires user; no submit clicked'};
  } else {
   // Persist authorization after inspecting/filling the actual form, just before the click.
   const reviewPath=path.join(workspace,'.career-assistant/review-input.json');
   await writeFile(reviewPath,JSON.stringify(setup.review));
   command(workspace,'prepare',setup.application_id,'--input',reviewPath);
   attemptId=command(workspace,'begin-submit',setup.application_id).attempt_id;
   await page.getByRole('button',{name:'Submit application'}).click();
   await page.locator('#result').filter({hasText: mode==='success'?'Application received':mode==='failed'?'not submitted':'Request pending'}).waitFor();
   const text=await page.locator('#result').textContent();
   if(mode==='success') {
    const evidence=path.join(workspace,'.career-assistant/evidence');await mkdir(evidence,{recursive:true});
    await page.screenshot({path:path.join(evidence,'receipt.png')});
    observation={result:'confirmed',detail:'Observed mock successful submission after upload',observed_confirmation:true,confirmation_text:text,confirmation_url:page.url(),evidence_path:'evidence/receipt.png',next_action:'Mock completed'};
   } else if(mode==='failed')observation={result:'failed',detail:text,verified_not_submitted:true};
   else observation={result:'unknown',detail:text,next_action:'Reconcile before retry'};
  }
  const input=path.join(workspace,'.career-assistant/outcome-input.json');await writeFile(input,JSON.stringify({...observation,...(attemptId?{attempt_id:attemptId}:{})}));
  const record=command(workspace,'outcome',setup.application_id,'--input',input);
  assert.equal(record.status,mode==='success'?'Submitted':mode==='failed'?'Blocked':'Needs user');
  if(mode==='unknown') {
   let rejected=false;
   try{command(workspace,'begin-submit',setup.application_id);}catch{rejected=true;}
   assert.equal(rejected,true);
  }
  passed.push('form-'+mode);await page.close();
 }
 // Deduplication is exercised through the actual CLI against the successful ledger.
 let duplicateRejected=false;
 try { command(path.join(dir,'success'),'application-add','demo-job'); } catch { duplicateRejected=true; }
 assert.equal(duplicateRejected,true);passed.push('duplicate-application');

 const workspace=path.join(dir,'credentials');await mkdir(path.join(workspace,'.career-assistant/credentials/workday'),{recursive:true});
 await writeFile(path.join(workspace,'.career-assistant/credentials/workday/accounts.txt'),'username: test@example.invalid, password: fictional-test-only\nusername: second@example.invalid, password: second-fictional-only\n');
 assert.equal(parseCredentials('username: test@example.invalid, password: fictional-test-only\nusername: test@example.invalid, password: fictional-test-only\n').length,1);
 const page=await browser.newPage();
 await page.route('https://fictional.wd5.myworkdayjobs.com/**',route=>route.fulfill({contentType:'text/html',body:'<input id="email" type="email"><input id="secret" type="password">'}));
 await page.goto('https://fictional.wd5.myworkdayjobs.com/login');
 const result=await fillWorkday(page,workspace,'https://fictional.wd5.myworkdayjobs.com',0,'#email','#secret');
 assert.deepEqual(result,{filled:true,values_omitted:true});
 assert.equal(await page.locator('#secret').evaluate(el=>el.value==='fictional-test-only'),true);
 await assert.rejects(fillWorkday(page,workspace,'https://unrelated.example.invalid',0,'#email','#secret'),/values omitted/);
 await assert.rejects(fillWorkday(page,workspace,'https://fictional.wd5.myworkdayjobs.com',8,'#email','#secret'),/values omitted/);
 passed.push('workday-memory-fill','workday-origin-guard','workday-attempt-index-guard');
 const origin='https://fictional.wd5.myworkdayjobs.com';
 const login=createWorkdayLoginSession();
 await login.fill(page,workspace,origin,0,'#email','#secret');
 await assert.rejects(login.fill(page,workspace,origin,1,'#email','#secret'),/values omitted/);
 login.observe(origin,'rejected');
 await assert.rejects(login.fill(page,workspace,origin,0,'#email','#secret'),/values omitted/);
 await login.fill(page,workspace,origin,1,'#email','#secret');
 assert.equal(await page.locator('#email').evaluate(el=>el.value==='second@example.invalid'),true);
 assert.equal(await page.locator('#secret').evaluate(el=>el.value==='second-fictional-only'),true);
 login.observe(origin,'success');
 await assert.rejects(login.fill(page,workspace,origin,0,'#email','#secret'),/values omitted/);
 passed.push('workday-exact-pairs-and-retry-ledger');
 for(const stop of ['captcha','2fa','sso','locked','network','unknown']) {
  const session=createWorkdayLoginSession();
  await session.fill(page,workspace,origin,0,'#email','#secret');
  assert.equal(session.observe(origin,stop).stopped,true);
  await assert.rejects(session.fill(page,workspace,origin,1,'#email','#secret'),/values omitted/);
  passed.push('workday-stop-'+stop);
 }
 // Browser exceptions may echo fill values: verify the public error is sanitized.
 const unsafePage={url:()=>origin+'/login',locator:selector=>({count:async()=>1,getAttribute:async()=>selector==='#secret'?'password':'email',fill:async()=>{throw new Error('fictional-test-only second-fictional-only');}})};
 await assert.rejects(fillWorkday(unsafePage,workspace,origin,0,'#email','#secret'),err=>!/fictional-test-only|second-fictional-only/.test(err.message)&&/values omitted/.test(err.message));
 const validation=JSON.parse(execFileSync(process.execPath,[path.join(root,'skills/career-assistant/scripts/local_credentials.mjs'),workspace],{encoding:'utf8',windowsHide:true}));
 assert.deepEqual(validation,{valid:true,pairs:2,values_omitted:true});
 passed.push('workday-sanitized-errors-and-cli');
 // Connect local credential filling, a mock login, resume upload, authorization and receipt.
 const flowWorkspace=path.join(dir,'workday-flow');
 const setup=run([path.join(root,'tests/browser_bridge.py'),flowWorkspace,'success']);
 command(flowWorkspace,'workday-init');
 const credentialsFile=path.join(flowWorkspace,'.career-assistant/credentials/workday/accounts.txt');
 await writeFile(credentialsFile,'username: flow@example.invalid, password: fictional-flow-only\n');
 command(flowWorkspace,'workday-init'); // Initialization must preserve a filled file.
 assert.equal(JSON.parse(execFileSync(process.execPath,[path.join(root,'skills/career-assistant/scripts/local_credentials.mjs'),flowWorkspace],{encoding:'utf8',windowsHide:true})).pairs,1);
 const flowPage=await browser.newPage();
 await flowPage.route(origin+'/**',route=>route.fulfill({contentType:'text/html',body:`<label>Email <input id="email" type="email"></label><label>Password <input id="secret" type="password"></label><button id="login">Sign in</button><script>document.querySelector('#login').onclick=()=>location.href=${JSON.stringify(url+'/?mode=success')};</script>`}));
 await flowPage.goto(origin+'/login');
 const flowLogin=createWorkdayLoginSession();
 await flowLogin.fill(flowPage,flowWorkspace,origin,0,'#email','#secret');
 await flowPage.locator('#login').click();
 await flowPage.locator('#application').waitFor();
 flowLogin.observe(origin,'success');
 await flowPage.locator('#name').fill('Fictional candidate');
 await flowPage.locator('#resume').setInputFiles(setup.pdf_path);
 const reviewPath=path.join(flowWorkspace,'.career-assistant/review.json');await writeFile(reviewPath,JSON.stringify(setup.review));
 command(flowWorkspace,'prepare',setup.application_id,'--input',reviewPath);
 const intent=command(flowWorkspace,'begin-submit',setup.application_id);
 await flowPage.getByRole('button',{name:'Submit application'}).click();
 await flowPage.locator('#result').filter({hasText:'Application received'}).waitFor();
 const evidence=path.join(flowWorkspace,'.career-assistant/evidence');await mkdir(evidence,{recursive:true});
 await flowPage.screenshot({path:path.join(evidence,'receipt.png')});
 const observation={attempt_id:intent.attempt_id,result:'confirmed',detail:'Local mock login and application flow',observed_confirmation:true,confirmation_text:await flowPage.locator('#result').textContent(),confirmation_url:flowPage.url(),evidence_path:'evidence/receipt.png',next_action:'Mock complete'};
 const outcomePath=path.join(flowWorkspace,'.career-assistant/outcome.json');await writeFile(outcomePath,JSON.stringify(observation));
 command(flowWorkspace,'outcome',setup.application_id,'--input',outcomePath);
 assert.equal(command(flowWorkspace,'status').applications.counts.Submitted,1);
 const tracker=await readFile(path.join(flowWorkspace,'.career-assistant/tracker.json'),'utf8');
 assert.equal(tracker.includes('fictional-flow-only'),false);
 assert.equal(tracker.includes('flow@example.invalid'),false);
 passed.push('workday-mock-login-to-submitted');
 console.log(JSON.stringify({passed:passed.length,scenarios:passed,scope:'Local mocks and fictional credentials only'},null,2));
} finally {
 if(browser)await browser.close();server.kill();
 assert.equal(path.dirname(path.resolve(dir)),path.resolve(os.tmpdir()));
 assert.ok(path.basename(dir).startsWith('career-browser-'));
 await rm(dir,{recursive:true,force:true});
}
