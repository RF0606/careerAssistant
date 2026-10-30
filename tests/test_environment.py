"""Dependency setup state/permission tests. Downloads and installers are stubbed here."""
import io
import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from unittest.mock import patch
from zipfile import ZipFile
from fixtures import make_workspace,assessment,draft
import environment as env
import capabilities
import jobs,resume
from storage import atomic,Store

PROJECT = Path(__file__).resolve().parents[1]


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.workspace=Path(self.temp.name)/'fictional-workspace'; self.workspace.mkdir()
        self.downloads=[]
        self.good={'packages':{'pypdf':True,'fitz':True},'version':[3,13,1],'python':sys.executable}

    def fake_command(self,args,env=None,timeout=300):
        args=list(map(str,args))
        if args[-1].endswith('probe.tex'):
            source=Path(args[-1]); source.with_suffix('.pdf').write_bytes(b'UNIT TEST PROBE; NOT REAL PDF QA')
        return subprocess.CompletedProcess(args,0,'tectonic test','')

    def venv_info(self, executable, installed):
        folder=Path(executable).parent.parent
        return {**self.good,'prefix':str(folder),'install_paths':{k:str(folder) for k in ['purelib','platlib','scripts','data']},
                'packages':{'pypdf':installed,'fitz':installed}}

    def ready(self,**kwargs):
        with patch.object(env,'probe_python',return_value=self.good), patch.object(env,'tool_path',return_value='fictional-tectonic'), patch.object(env,'_command',side_effect=self.fake_command), patch.object(env,'_fetch',side_effect=AssertionError('Unexpected download')):
            return env.setup(self.workspace,browser='existing',search='existing',**kwargs)

    def test_ready_tools_are_reused_without_downloads_or_profile_creation(self):
        first=self.ready(); second=self.ready()
        self.assertEqual('ready',first['status']); self.assertEqual('ready',second['status'])
        self.assertEqual('available',second['steps']['python_packages']['status'])
        self.assertFalse((env.root(self.workspace)/'profile.json').exists())
        self.assertFalse((env.root(self.workspace)/'routes').exists())
        self.assertIn('/.career-assistant/',(self.workspace/'.gitignore').read_text())
        self.assertFalse((env.root(self.workspace)/'setup/.install.lock').exists())

    def test_library_import_output_cannot_corrupt_machine_readable_probe(self):
        modules=self.workspace/'noisy-modules';modules.mkdir()
        for name in ['pypdf','pymupdf']:
            (modules/(name+'.py')).write_text("print('Fictional library import notice')\n")
        with patch.dict(os.environ,{'PYTHONPATH':str(modules)}):
            result=env.probe_python(sys.executable)
        self.assertIsNotNone(result)
        self.assertTrue(all(result['packages'].values()))

    def test_doctor_keeps_library_notices_out_of_json_output(self):
        output=io.StringIO()
        def noisy(name):print('Fixture import notice');return object()
        with patch.object(capabilities.importlib,'import_module',side_effect=noisy),contextlib.redirect_stdout(output):
            result=capabilities.report(self.workspace)
        self.assertEqual('',output.getvalue())
        self.assertTrue(all(result['packages'].values()))

    def test_denied_step_is_saved_and_successful_retry_clears_old_permission_prompt(self):
        person=make_workspace(self.workspace/'person')
        self.workspace=person.workspace
        original=(person.root/'profile.json').read_bytes()
        failure=env.SetupError('approval_required','Fictional denied write','Ask for this installation permission')
        with patch.object(env,'_install_packages',side_effect=failure), patch.object(env,'_install_tectonic',return_value={'status':'available','executable':'trusted-tectonic'}):
            result=env.setup(self.workspace,browser='defer',search='defer')
        self.assertEqual('approval_required',result['status'])
        self.assertTrue(result['state_saved'])
        self.assertEqual(original,(person.root/'profile.json').read_bytes())
        repaired=self.ready()
        self.assertEqual('ready',repaired['status'])
        self.assertNotIn('reason',repaired['steps']['python_packages'])
        self.assertNotIn('next_action',repaired['steps']['python_packages'])
        self.assertEqual(original,(person.root/'profile.json').read_bytes())

    def test_denied_workspace_never_claims_saved_setup_or_runs_installers(self):
        with patch.object(env,'atomic_text',side_effect=PermissionError('Fixture denial')), patch.object(env,'_install_packages') as install:
            result=env.setup(self.workspace,browser='existing',search='existing')
        self.assertEqual('approval_required',result['status'])
        self.assertFalse(result['state_saved']); install.assert_not_called()

    def test_localized_command_permission_error_requests_permission_without_output_leak(self):
        completed=subprocess.CompletedProcess(['fictional-installer'],1,'','[WinError 5] 拒绝访问。 private-sentinel')
        with patch.object(env.subprocess,'run',return_value=completed):
            with self.assertRaises(env.SetupError) as failure:env._command(['fictional-installer'])
        self.assertEqual('approval_required',failure.exception.result['status'])
        self.assertNotIn('private-sentinel',json.dumps(failure.exception.result))

    def test_existing_install_lock_is_not_stolen(self):
        lock=env.root(self.workspace)/'setup/.install.lock';lock.parent.mkdir(parents=True);lock.write_text('fixture pid')
        with patch.object(env,'_install_packages') as install:
            result=env.setup(self.workspace)
        self.assertEqual('setup_in_progress',result['status'])
        self.assertEqual('fixture pid',lock.read_text());install.assert_not_called()

    def test_missing_tools_offline_are_not_misreported_as_permission_or_success(self):
        with patch.object(env,'_install_packages',return_value={'status':'available','python_executable':sys.executable}), patch.object(env,'tool_path',return_value=None), patch.object(env,'_fetch') as fetch:
            result=env.setup(self.workspace,browser='defer',search='defer',downloads=False)
        self.assertEqual('partial',result['status'])
        self.assertEqual('download_required',result['steps']['tectonic']['status'])
        self.assertEqual('waiting_for_dependencies',result['steps']['tex_cache']['status'])
        fetch.assert_not_called()

    def test_user_deferral_persists_until_explicit_resume_without_silent_download(self):
        options=[]
        def packages(workspace,downloads):
            options.append(downloads)
            return {'status':'available','python_executable':sys.executable}
        with patch.object(env,'_install_packages',side_effect=packages),patch.object(env,'_install_tectonic',return_value={'status':'available','executable':'tectonic'}),patch.object(env,'_warm_tex',return_value={'status':'available'}),patch.object(env,'_install_browser') as browser:
            first=env.setup(self.workspace,browser='missing',search='defer',defer=True)
            second=env.setup(self.workspace,browser='missing',search='defer')
            self.assertEqual('deferred',first['installation_policy'])
            self.assertEqual('deferred',second['installation_policy'])
            self.assertEqual([False,False],options)
            browser.assert_not_called()
            resumed=env.setup(self.workspace,browser='existing',search='existing',resume=True)
        self.assertTrue(options[-1])
        self.assertEqual('auto',resumed['installation_policy'])

    def test_later_pdf_compilation_respects_user_download_deferral(self):
        person=make_workspace(self.workspace/'person');jobs.assess(person,assessment(person))
        atomic(person.root/'setup/environment.json',{'schema_version':1,'installation_policy':'deferred','steps':{}})
        failed=subprocess.CompletedProcess([],1,'','No cached fixture resource')
        with patch.object(resume.shutil,'which',return_value='tectonic'),patch.dict(sys.modules,{'pymupdf':object()}),patch.object(resume.subprocess,'run',return_value=failed) as compiler:
            with self.assertRaisesRegex(ValueError,'Downloads are deferred'):resume.render(person,'demo-job',draft(person))
        self.assertIn('--only-cached',compiler.call_args.args[0])
        self.assertEqual('draft',person.read('packages/demo-job/validation.json')['status'])

    def test_missing_pdf_packages_use_a_local_venv_and_official_binary_wheels(self):
        selected=list(env.local_python(self.workspace))[0];installed=False;commands=[]
        def probe(exe):
            return self.venv_info(exe,installed)
        def create(folder):
            selected.parent.mkdir(parents=True,exist_ok=True);selected.write_text('Fixture interpreter marker')
        def command(args,**kwargs):
            nonlocal installed
            commands.append(list(map(str,args)));installed=True
            return subprocess.CompletedProcess(args,0,'','')
        with patch.object(env,'probe_python',side_effect=probe), patch.object(env.venv.EnvBuilder,'create',side_effect=create), patch.object(env,'_command',side_effect=command):
            result=env._install_packages(self.workspace)
        self.assertEqual(str(selected),result['python_executable'])
        self.assertEqual('installed',result['status'])
        installation=next(command for command in commands if 'install' in command)
        self.assertIn('https://pypi.org/simple',installation)
        self.assertIn('--only-binary=:all:',installation)
        self.assertEqual(str(selected),installation[0])

    def test_incomplete_system_python_requests_local_bootstrap_without_global_pip(self):
        missing={**self.good,'packages':{'pypdf':False,'fitz':False}}
        with patch.object(env,'probe_python',return_value=missing),patch.object(env,'venv',None):
            with self.assertRaises(env.SetupError) as failure:env._install_packages(self.workspace)
        self.assertEqual('runtime_required',failure.exception.result['status'])
        self.assertTrue(any('bootstrap-python.' in argument for argument in failure.exception.result['command']))
        self.assertNotIn('sudo',failure.exception.result['command'])

    def test_interrupted_venv_with_missing_pip_is_repaired_before_install(self):
        selected=next(env.local_python(self.workspace));selected.parent.mkdir(parents=True);selected.write_text('Fixture interpreter')
        installed=False;calls=[]
        def probe(executable):return self.venv_info(executable,installed)
        def command(args,**kwargs):
            nonlocal installed
            args=list(map(str,args));calls.append(args)
            if args[-2:]==['pip','--version']:raise env.SetupError('retryable_error','pip missing','Repair local pip')
            if 'install' in args:installed=True
            return subprocess.CompletedProcess(args,0,'','')
        with patch.object(env,'probe_python',side_effect=probe),patch.object(env,'_command',side_effect=command):
            result=env._install_packages(self.workspace)
        self.assertEqual('installed',result['status'])
        self.assertTrue(any('ensurepip' in call for call in calls))

    def test_offline_template_probe_precedes_download_and_private_cache_is_retained(self):
        calls=[];saved=[]
        def command(args,**kwargs):
            calls.append((list(map(str,args)),kwargs.get('env',{})))
            if '--only-cached' in args:
                raise env.SetupError('retryable_error','empty cache','Permit download')
            Path(args[-1]).with_suffix('.pdf').write_bytes(b'UNIT TEST PROBE')
            return subprocess.CompletedProcess(args,0,'','')
        with patch.object(env,'_command',side_effect=command):
            result=env._warm_tex(self.workspace,'tectonic',save=saved.append)
        self.assertIn('--only-cached',calls[0][0])
        self.assertEqual(str(env.root(self.workspace)/'tools/tex-cache'),calls[1][1]['TECTONIC_CACHE_DIR'])
        self.assertEqual('workspace',saved[0]['cache_scope'])
        self.assertEqual('installed',result['status'])
        self.assertFalse((env.root(self.workspace)/'profile.json').exists())

    def test_offline_template_probe_does_not_fall_back_after_permission_denial(self):
        denial=env.SetupError('approval_required','Denied','Ask user')
        with patch.object(env,'_command',side_effect=denial) as command:
            with self.assertRaises(env.SetupError) as failure:env._warm_tex(self.workspace,'tectonic')
        self.assertEqual('approval_required',failure.exception.result['status'])
        self.assertEqual(1,command.call_count)

    def test_wrong_asset_hash_never_installs_or_executes_binary(self):
        suffix={'Windows':'x86_64-pc-windows-msvc.zip','Darwin':'x86_64-apple-darwin.tar.gz','Linux':'x86_64-unknown-linux-musl.tar.gz'}[env.platform.system()]
        release={'assets':[{'name':'tectonic-test-'+suffix,'digest':'sha256:'+'0'*64,'browser_download_url':'https://github.com/tectonic-typesetting/tectonic/releases/download/test/tool.zip'}]}
        with patch.object(env,'tool_path',return_value=None), patch.object(env.platform,'machine',return_value='x86_64'), patch.object(env,'_fetch',side_effect=[json.dumps(release).encode(),b'not the expected asset']),patch.object(env,'_command') as execute:
            with self.assertRaises(env.SetupError) as failure:env._install_tectonic(self.workspace)
        self.assertEqual('verification_failed',failure.exception.result['status'])
        execute.assert_not_called()
        self.assertFalse((env.root(self.workspace)/'tools/tectonic').exists())

    def test_unapproved_download_origin_is_rejected_before_network(self):
        with patch.object(env.urllib.request,'urlopen') as network:
            for url in ['http://github.com/tool','https://evil.invalid/tool','https://github.com.evil.invalid/tool']:
                with self.subTest(url=url),self.assertRaises(env.SetupError):env._fetch(url)
        network.assert_not_called()

    def test_archive_traversal_cannot_write_outside_install_directory(self):
        archive=self.workspace/'unsafe.zip'
        with ZipFile(archive,'w') as z:z.writestr('../../outside.txt',b'Untrusted fixture')
        with self.assertRaises(env.SetupError):env._unpack(archive,self.workspace/'install')
        self.assertFalse((self.workspace.parent/'outside.txt').exists())

    def test_unknown_platform_is_reported_without_unverified_download(self):
        with patch.object(env,'tool_path',return_value=None),patch.object(env.platform,'machine',return_value='unknown-cpu'),patch.object(env,'_fetch') as network:
            with self.assertRaises(env.SetupError) as failure:env._install_tectonic(self.workspace)
        self.assertEqual('unsupported',failure.exception.result['status']);network.assert_not_called()

    def test_existing_browser_does_not_install_a_second_browser(self):
        with patch.object(env,'_install_browser') as install:
            self.ready()
        install.assert_not_called()

    def test_missing_search_connector_can_use_an_existing_host_browser(self):
        with patch.object(env,'_install_packages',return_value={'status':'available','python_executable':sys.executable}),patch.object(env,'_install_tectonic',return_value={'status':'available','executable':'tectonic'}),patch.object(env,'_warm_tex',return_value={'status':'available'}):
            result=env.setup(self.workspace,browser='existing',search='missing')
        self.assertEqual('available_via_browser',result['steps']['search']['status'])
        self.assertEqual('ready',result['status'])

    def test_new_browser_is_not_claimed_live_before_host_reload(self):
        with patch.object(env,'_install_packages',return_value={'status':'available','python_executable':sys.executable}),patch.object(env,'_install_tectonic',return_value={'status':'available','executable':'tectonic'}),patch.object(env,'_warm_tex',return_value={'status':'available'}),patch.object(env,'_install_browser',return_value={'status':'host_reload_required','installed':True,'project_configured':True}):
            result=env.setup(self.workspace,browser='missing',search='missing')
        self.assertEqual('host_reload_required',result['status'])
        self.assertEqual('host_connection_required',result['steps']['search']['status'])
        self.assertEqual('user_action_when_target_known',result['steps']['login']['status'])

    def test_project_mcp_registration_preserves_existing_servers_and_security_settings(self):
        codex=self.workspace/'.codex/config.toml';codex.parent.mkdir()
        original='model = \"fixture-model\"\n[mcp_servers.existing]\ncommand = \"trusted-existing\"\n'
        codex.write_text(original)
        claude=self.workspace/'.mcp.json';atomic(claude,{'mcpServers':{'existing':{'command':'trusted-existing'}}})
        server={'command':str(self.workspace/'node'),'args':['private-cli','--user-data-dir',str(env.root(self.workspace)/'browser/profile')],'env':{'PLAYWRIGHT_BROWSERS_PATH':str(env.root(self.workspace)/'browser/engines')}}
        env._register_browser(self.workspace,'both',server)
        first=codex.read_bytes()
        env._register_browser(self.workspace,'both',server)
        self.assertEqual(first,codex.read_bytes())
        self.assertIn(original,codex.read_text())
        self.assertEqual('trusted-existing',json.loads(claude.read_text())['mcpServers']['existing']['command'])
        self.assertIn('/.mcp.json',(self.workspace/'.gitignore').read_text())

    def test_missing_browser_os_libraries_expose_the_exact_permission_scoped_command(self):
        directory=env.root(self.workspace)/'tools/browser/node_modules'
        module=directory/'@playwright/mcp';module.mkdir(parents=True)
        (module/'package.json').write_text('{"bin":{"playwright-mcp":"cli.js"}}')
        library=directory/'playwright';library.mkdir();(library/'cli.js').write_text('Fixture only')
        (library/'package.json').write_text('{"engines":{"node":">=20"}}')
        failure=env.SetupError('system_dependencies_required','Missing OS libraries','Check current system install permission')
        for commands in [[failure],[env.SetupError('retryable_error','Engine missing','Download it'),subprocess.CompletedProcess([],0,'',''),failure]]:
            preflight=[subprocess.CompletedProcess([],0,'v22.1.0',''),subprocess.CompletedProcess([],0,'0.0.83','')]
            with self.subTest(commands=len(commands)),patch.object(env,'_node',return_value=('fixture-node','fixture-npm')),patch.object(env,'_command',side_effect=preflight+commands),patch.object(env,'_register_browser') as register:
                with self.assertRaises(env.SetupError) as caught:env._install_browser(self.workspace,'codex',True)
            self.assertEqual(['fixture-node',str(library/'cli.js'),'install-deps','chromium'],caught.exception.result['system_dependency_command'])
            register.assert_not_called()

    def test_conflicting_project_browser_config_requires_review_without_overwrite(self):
        p=self.workspace/'.codex/config.toml';p.parent.mkdir();p.write_text('[mcp_servers.career_browser]\ncommand = \"user-selected\"\n')
        before=p.read_bytes()
        with self.assertRaises(env.SetupError) as failure:env._register_browser(self.workspace,'codex',{'command':'new','args':[],'env':{}})
        self.assertEqual('configuration_review_required',failure.exception.result['status'])
        self.assertEqual(before,p.read_bytes())

    def test_runtime_selection_never_executes_an_arbitrary_saved_path(self):
        path=env.root(self.workspace)/'setup/environment.json'
        atomic(path,{'schema_version':1,'installation_policy':'auto','steps':{'python_packages':{'status':'available','python_executable':str(self.workspace.parent/'untrusted.exe')}}})
        self.assertIsNone(env.configured_python(self.workspace))

    def test_operational_setup_state_cannot_be_mistaken_for_old_career_schema(self):
        self.ready()
        for name in ['setup/environment.json',Path('setup/environment.json')]:
            with self.subTest(name=str(name)),self.assertRaisesRegex(ValueError,'operational metadata'):
                Store(self.workspace).read(name)

    def test_denied_python_probe_does_not_install_an_alternative_to_bypass_it(self):
        denial=env.SetupError('approval_required','Fictional runtime policy denial','Ask user')
        with patch.object(env,'_command',side_effect=denial),patch.object(env.venv.EnvBuilder,'create') as create:
            with self.assertRaises(env.SetupError) as failure:env._install_packages(self.workspace)
        self.assertEqual('approval_required',failure.exception.result['status'])
        create.assert_not_called()

    def test_denied_existing_node_does_not_download_a_replacement(self):
        denial=env.SetupError('approval_required','Fictional Node denial','Ask user')
        with patch.object(env.shutil,'which',return_value=sys.executable),patch.object(env,'_command',side_effect=denial),patch.object(env,'_fetch') as download:
            with self.assertRaises(env.SetupError):env._node(self.workspace,True)
        download.assert_not_called()

    def test_native_python_bootstrap_detects_existing_runtime_without_install(self):
        scripts=PROJECT/'skills/career-assistant/scripts'
        if os.name=='nt':
            command=[shutil.which('powershell') or shutil.which('pwsh'),'-NoProfile','-File',str(scripts/'bootstrap-python.ps1'),'-Workspace',str(self.workspace),'-Python',sys.executable,'-CheckOnly']
        else:
            command=[shutil.which('sh'),str(scripts/'bootstrap-python.sh'),str(self.workspace),sys.executable,'--check-only']
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual('available',json.loads(result.stdout)['status'])
        self.assertFalse((self.workspace/'.career-assistant').exists())

    def test_native_missing_python_check_does_not_install_or_claim_progress(self):
        empty=self.workspace/'empty-path';empty.mkdir()
        scripts=PROJECT/'skills/career-assistant/scripts'
        if os.name=='nt':
            command=[shutil.which('powershell') or shutil.which('pwsh'),'-NoProfile','-File',str(scripts/'bootstrap-python.ps1'),'-Workspace',str(self.workspace),'-CheckOnly']
        else:
            command=[shutil.which('sh'),str(scripts/'bootstrap-python.sh'),str(self.workspace),'--check-only']
        result=subprocess.run(command,env=dict(os.environ,PATH=str(empty)),capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(2,result.returncode,result.stderr)
        self.assertEqual('python_missing',json.loads(result.stdout)['status'])
        self.assertFalse((self.workspace/'.career-assistant/setup/environment.json').exists())

    def test_native_bootstrap_honors_saved_user_deferral_before_downloading(self):
        atomic(env.root(self.workspace)/'setup/environment.json',{'installation_policy':'deferred','steps':{}})
        scripts=PROJECT/'skills/career-assistant/scripts'
        if os.name=='nt':
            command=[shutil.which('powershell') or shutil.which('pwsh'),'-NoProfile','-File',str(scripts/'bootstrap-python.ps1'),'-Workspace',str(self.workspace),'-ManagedPython']
        else:
            command=[shutil.which('sh'),str(scripts/'bootstrap-python.sh'),str(self.workspace),'','--managed']
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(2,result.returncode,result.stderr)
        self.assertEqual('installation_deferred',json.loads(result.stdout)['status'])
        self.assertFalse((env.root(self.workspace)/'tools').exists())

    def test_invalid_saved_choices_never_enable_installation_or_overwrite_state(self):
        values=['{"installation_policy":"deferred","steps":',
                json.dumps({'schema_version':1,'installation_policy':'deferred','steps':[]}),
                json.dumps({'schema_version':99,'installation_policy':'auto','steps':{}}),
                json.dumps({'schema_version':1,'steps':{}}),
                json.dumps({'schema_version':1,'installation_policy':None,'steps':{}}),
                json.dumps({'schema_version':1,'installation_policy':'auto','steps':{'browser':[]}})]
        path=env.root(self.workspace)/'setup/environment.json';path.parent.mkdir(parents=True)
        for value in values:
            path.write_text(value,encoding='utf-8');before=path.read_bytes()
            with self.subTest(value=value),patch.object(env,'_install_packages') as install,patch.object(env,'_fetch') as download:
                result=env.setup(self.workspace,browser='missing',search='missing',resume=True)
            self.assertEqual('configuration_review_required',result['status'])
            self.assertFalse(result['state_saved']);self.assertEqual(before,path.read_bytes())
            install.assert_not_called();download.assert_not_called()
        self.assertFalse((self.workspace/'.gitignore').exists())

    def test_unreadable_saved_choices_do_not_authorize_installation(self):
        path=env.root(self.workspace)/'setup/environment.json'
        atomic(path,{'schema_version':1,'installation_policy':'deferred','steps':{}})
        original=Path.read_text;before=path.read_bytes()
        def denied(file,*args,**kwargs):
            if file==path:raise PermissionError('Fixture denied state read')
            return original(file,*args,**kwargs)
        with patch.object(Path,'read_text',denied),patch.object(env,'_install_packages') as install:
            result=env.setup(self.workspace,browser='missing')
        self.assertEqual('approval_required',result['status']);install.assert_not_called()
        self.assertEqual(before,path.read_bytes())

    def test_explicit_state_recovery_backs_up_raw_bytes_and_installs_nothing(self):
        for choice,policy in [('defer','deferred'),('resume','auto')]:
            workspace=self.workspace/choice;path=env.root(workspace)/'setup/environment.json'
            path.parent.mkdir(parents=True);original=b'{"installation_policy":"deferred", BROKEN'
            path.write_bytes(original)
            fact=env.root(workspace)/'profile.json';fact.write_bytes(b'Fictional untouched career sentinel')
            with patch.object(env,'_install_packages') as install,patch.object(env,'_fetch') as download:
                result=env.recover_setup(workspace,choice,'Fictional user explicitly confirms this recovery choice')
            self.assertEqual('recovered',result['status']);self.assertTrue(result['state_saved'])
            self.assertEqual(original,Path(result['backup_path']).read_bytes())
            self.assertEqual(policy,env.settings(workspace)['installation_policy'])
            self.assertEqual(b'Fictional untouched career sentinel',fact.read_bytes())
            install.assert_not_called();download.assert_not_called()

    def test_state_recovery_requires_confirmation_and_retains_original_on_write_denial(self):
        path=env.root(self.workspace)/'setup/environment.json';path.parent.mkdir(parents=True);path.write_bytes(b'Broken fixture state')
        with self.assertRaises(ValueError):env.recover_setup(self.workspace,'resume','')
        before=path.read_bytes()
        with patch.object(env,'atomic',side_effect=PermissionError('Fixture denied recovery write')):
            result=env.recover_setup(self.workspace,'defer','Fictional user chooses deferral')
        self.assertEqual('approval_required',result['status']);self.assertFalse(result['state_saved'])
        self.assertEqual(before,path.read_bytes())

    def test_valid_state_is_not_reset_by_recovery(self):
        self.ready();path=env.root(self.workspace)/'setup/environment.json';before=path.read_bytes()
        result=env.recover_setup(self.workspace,'resume','Fictional recovery request')
        self.assertEqual('not_required',result['status']);self.assertEqual(before,path.read_bytes())

    def test_doctor_reports_broken_state_without_pdf_ready_or_any_repair(self):
        path=env.root(self.workspace)/'setup/environment.json';path.parent.mkdir(parents=True);path.write_bytes(b'{broken')
        before=path.read_bytes()
        with patch.object(env,'_fetch') as download:
            result=capabilities.report(self.workspace,check_pdf=True)
        self.assertTrue(result['features']['profile_text_docx_and_scoring'])
        self.assertFalse(result['features']['pdf_generation_and_qa'])
        self.assertEqual('configuration_review_required',result['setup']['status'])
        self.assertEqual(before,path.read_bytes());download.assert_not_called()

    def test_core_text_and_source_only_work_continue_while_setup_requires_review(self):
        person=make_workspace(self.workspace/'person');jobs.assess(person,assessment(person))
        path=person.root/'setup/environment.json';path.parent.mkdir(parents=True);path.write_bytes(b'{broken')
        resume.render(person,'demo-job',draft(person),False)
        self.assertTrue((person.root/'packages/demo-job/resume.tex').is_file())
        script=PROJECT/'skills/career-assistant/scripts/career.py'
        text=person.root/'statement-extra.txt';text.write_text('Fictional additional source statement only',encoding='utf-8')
        result=subprocess.run([sys.executable,str(script),'--workspace',str(person.workspace),'import-source',str(text)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual(b'{broken',path.read_bytes())

    def test_pdf_cli_returns_structured_review_without_traceback(self):
        path=env.root(self.workspace)/'setup/environment.json';path.parent.mkdir(parents=True);path.write_bytes(b'{broken')
        payload=self.workspace/'draft.json';payload.write_text('{}')
        result=subprocess.run([sys.executable,str(PROJECT/'skills/career-assistant/scripts/career.py'),'--workspace',str(self.workspace),'render','fixture','--input',str(payload)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(1,result.returncode)
        self.assertEqual('configuration_review_required',json.loads(result.stderr)['status'])
        self.assertNotIn('Traceback',result.stderr)

    def test_mcp_semantic_equivalence_preserves_quoted_dotted_and_inline_tables(self):
        representations=['[mcp_servers."career_browser"]\ncommand="fixture"\nargs=[]\n',
                         "[mcp_servers.'career_browser']\ncommand='fixture'\nargs=[]\n",
                         'mcp_servers.career_browser.command="fixture"\nmcp_servers.career_browser.args=[]\n',
                         'mcp_servers={career_browser={command="fixture",args=[]}}\n']
        for index,text in enumerate(representations):
            workspace=self.workspace/str(index);path=workspace/'.codex/config.toml';path.parent.mkdir(parents=True);path.write_text(text)
            before=path.read_bytes()
            env._register_browser(workspace,'codex',{'command':'fixture','args':[],'env':{}})
            self.assertEqual(before,path.read_bytes())
            self.assertIn('career_browser',env._toml.loads(path.read_text())['mcp_servers'])

    def test_quoted_server_conflict_preserves_original_without_duplicate_header(self):
        path=self.workspace/'.codex/config.toml';path.parent.mkdir();path.write_text('[mcp_servers."career_browser"]\ncommand="user-selected"\nargs=[]\n')
        before=path.read_bytes()
        with self.assertRaises(env.SetupError):env._register_browser(self.workspace,'codex',{'command':'new','args':[],'env':{}})
        self.assertEqual(before,path.read_bytes());self.assertFalse((self.workspace/'.gitignore').exists())

    def test_invalid_existing_or_unappendable_inline_parent_is_not_written(self):
        path=self.workspace/'.codex/config.toml';path.parent.mkdir()
        for text in ['[broken table','mcp_servers={other={command="user-selected"}}\n']:
            path.write_text(text);before=path.read_bytes()
            with self.assertRaises(env.SetupError):env._register_browser(self.workspace,'codex',{'command':'fixture','args':[],'env':{}})
            self.assertEqual(before,path.read_bytes())

    def test_all_requested_hosts_are_preflighted_before_any_config_write(self):
        codex=self.workspace/'.codex/config.toml';codex.parent.mkdir();codex.write_text('model="fixture"\n')
        claude=self.workspace/'.mcp.json';claude.write_text('{broken')
        before=codex.read_bytes()
        with self.assertRaises(env.SetupError):env._register_browser(self.workspace,'both',{'command':'fixture','args':[],'env':{}})
        self.assertEqual(before,codex.read_bytes());self.assertFalse((self.workspace/'.gitignore').exists())

    def test_comment_mentioning_server_does_not_block_safe_registration(self):
        path=self.workspace/'.codex/config.toml';path.parent.mkdir();path.write_text('# [mcp_servers.career_browser] is only a comment\nmodel="fixture"\n')
        env._register_browser(self.workspace,'codex',{'command':'fixture','args':[],'env':{}})
        result=env._toml.loads(path.read_text())
        self.assertEqual('fixture',result['model']);self.assertEqual('fixture',result['mcp_servers']['career_browser']['command'])

    def test_selected_runtime_toml_parser_returns_only_boolean_metadata(self):
        text='[mcp_servers."career_browser"]\ncommand="fixture-secret"\nargs=[]\n'
        server={'command':'fixture-secret','args':[],'env':{}}
        with patch.object(env,'_toml',None),patch.object(env,'configured_python',return_value=Path(sys.executable)):
            result=env._inspect_toml(self.workspace,text,server)
        self.assertTrue(result['same']);self.assertNotIn('fixture-secret',json.dumps(result))

    def test_native_bootstrap_stops_on_damaged_choices_without_runtime_download(self):
        path=env.root(self.workspace)/'setup/environment.json';path.parent.mkdir(parents=True);path.write_text('{broken')
        scripts=PROJECT/'skills/career-assistant/scripts'
        command=([shutil.which('powershell') or shutil.which('pwsh'),'-NoProfile','-File',str(scripts/'bootstrap-python.ps1'),'-Workspace',str(self.workspace),'-ManagedPython'] if os.name=='nt'
                 else [shutil.which('sh'),str(scripts/'bootstrap-python.sh'),str(self.workspace),'','--managed'])
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(2,result.returncode,result.stderr)
        self.assertEqual('configuration_review_required',json.loads(result.stdout)['status'])
        self.assertFalse((env.root(self.workspace)/'tools').exists())

    def test_linked_host_configuration_cannot_modify_settings_outside_workspace(self):
        other=Path(self.temp.name)/'other-host-config';other.mkdir()
        outside=other/'config.toml';outside.write_text('model="outside-fixture"\n');before=outside.read_bytes()
        link=self.workspace/'.codex'
        if os.name=='nt':
            import _winapi
            _winapi.CreateJunction(str(other),str(link))
        else:link.symlink_to(other,target_is_directory=True)
        with self.assertRaises(env.SetupError):env._register_browser(self.workspace,'codex',{'command':'fixture','args':[],'env':{}})
        self.assertEqual(before,outside.read_bytes())

    def test_ambiguous_state_stops_before_every_installer_and_preserves_raw_bytes(self):
        invalid=[b'{"schema_version":1,"installation_policy":"deferred","steps":{},"installation_policy":"auto"}',
                 b'{"schema_version":true,"installation_policy":"auto","steps":{}}',
                 b'{"schema_version":1.0,"installation_policy":"auto","steps":{}}',
                 b'{"schema_version":1,"installation_policy":"auto","steps":{"interrupted-step":{}}}',
                 b'{"schema_version":1,"installation_policy":"auto","steps":{"browser":{}}}',
                 b'{"schema_version":1,"installation_policy":"auto","steps":{"browser":{"status":""}}}',
                 b'{"schema_version":1,"installation_policy":"auto","steps":{"browser":{"status":"deferred","status":"available"}}}',
                 b'{"schema_version":1,"installation_policy":"auto","steps":{},"extra":NaN}']
        for index,original in enumerate(invalid):
            with self.subTest(index=index):
                workspace=self.workspace/str(index);state=env.root(workspace)/'setup/environment.json'
                state.parent.mkdir(parents=True);state.write_bytes(original)
                with patch.object(env,'_install_packages') as packages,patch.object(env,'_install_tectonic') as compiler,patch.object(env,'_install_browser') as browser,patch.object(env,'_fetch') as download:
                    result=env.setup(workspace,browser='missing',search='missing',resume=True)
                self.assertEqual('configuration_review_required',result['status'])
                self.assertFalse(result['state_saved']);self.assertEqual(original,state.read_bytes())
                self.assertFalse((workspace/'.gitignore').exists())
                self.assertEqual(['environment.json'],sorted(p.name for p in state.parent.iterdir()))
                for installer in [packages,compiler,browser,download]:installer.assert_not_called()

    def test_ambiguous_state_needs_explicit_recovery_and_keeps_exact_original(self):
        original=b'{"schema_version":1,"installation_policy":"deferred","steps":{},"installation_policy":"auto"}'
        state=env.root(self.workspace)/'setup/environment.json';state.parent.mkdir(parents=True);state.write_bytes(original)
        result=env.recover_setup(self.workspace,'defer','Fictional user explicitly chooses continued deferral')
        self.assertEqual('recovered',result['status']);self.assertEqual(original,Path(result['backup_path']).read_bytes())
        self.assertEqual('deferred',env.settings(self.workspace)['installation_policy'])

    def link_directory(self, target, link):
        link.parent.mkdir(parents=True,exist_ok=True)
        if os.name=='nt':
            import _winapi
            _winapi.CreateJunction(str(target),str(link))
        else:link.symlink_to(target,target_is_directory=True)

    def test_absent_state_under_linked_parents_never_writes_a_lock_or_state_outside(self):
        for index,relative in enumerate(['.career-assistant','.career-assistant/setup']):
            with self.subTest(relative=relative):
                workspace=self.workspace/str(index);workspace.mkdir()
                outside=Path(self.temp.name)/('outside-'+str(index));outside.mkdir()
                self.link_directory(outside,workspace/relative)
                with patch.object(env,'_install_packages') as install,patch.object(env,'_fetch') as download:
                    result=env.setup(workspace,browser='missing')
                self.assertEqual('configuration_review_required',result['status']);self.assertFalse(result['state_saved'])
                self.assertEqual([],list(outside.iterdir()));self.assertFalse((workspace/'.gitignore').exists())
                install.assert_not_called();download.assert_not_called()

    def test_recovery_never_writes_through_linked_backup_directory(self):
        path=env.root(self.workspace)/'setup/environment.json';path.parent.mkdir(parents=True);path.write_bytes(b'{broken')
        outside=Path(self.temp.name)/'outside-backups';outside.mkdir()
        self.link_directory(outside,path.parent/'state-backups')
        result=env.recover_setup(self.workspace,'defer','Fictional recovery request')
        self.assertEqual('configuration_review_required',result['status']);self.assertFalse(result['state_saved'])
        self.assertEqual(b'{broken',path.read_bytes());self.assertEqual([],list(outside.iterdir()))
        self.assertFalse((path.parent/'.install.lock').exists())

    def native_command(self,workspace):
        scripts=PROJECT/'skills/career-assistant/scripts'
        if os.name=='nt':return [shutil.which('powershell') or shutil.which('pwsh'),'-NoProfile','-File',str(scripts/'bootstrap-python.ps1'),'-Workspace',str(workspace),'-ManagedPython']
        return [shutil.which('sh'),str(scripts/'bootstrap-python.sh'),str(workspace),'','--managed']

    def test_native_runtime_bootstrap_rejects_linked_setup_before_writing(self):
        outside=Path(self.temp.name)/'outside-native';outside.mkdir()
        self.link_directory(outside,env.root(self.workspace)/'setup')
        result=subprocess.run(self.native_command(self.workspace),capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(2,result.returncode,result.stderr)
        self.assertEqual('configuration_review_required',json.loads(result.stdout)['status'])
        self.assertEqual([],list(outside.iterdir()));self.assertFalse((env.root(self.workspace)/'tools').exists())

    def test_native_runtime_bootstrap_never_infers_consent_from_ambiguous_existing_json(self):
        path=env.root(self.workspace)/'setup/environment.json';path.parent.mkdir(parents=True)
        raw=b'{"schema_version":1,"installation_policy":"deferred","steps":{},"installation_policy":"auto"}'
        path.write_bytes(raw)
        result=subprocess.run(self.native_command(self.workspace),capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(2,result.returncode,result.stderr)
        self.assertIn(json.loads(result.stdout)['status'],['configuration_review_required','installation_deferred'])
        self.assertEqual(raw,path.read_bytes());self.assertFalse((env.root(self.workspace)/'tools').exists())

    @unittest.skipUnless(os.name=='nt','Actual Windows shell and GBK pipe behavior')
    def test_native_python_probe_round_trips_chinese_paths_with_gbk_in_both_shells(self):
        workspace=self.workspace/"中文 空格'验收";workspace.mkdir()
        venv.EnvBuilder(with_pip=False).create(workspace/'.venv')
        python=workspace/'.venv/Scripts/python.exe'
        environment=dict(os.environ,PYTHONIOENCODING='gbk',PYTHONUTF8='0')
        script=PROJECT/'skills/career-assistant/scripts/bootstrap-python.ps1'
        shells=list(dict.fromkeys(shutil.which(name) for name in ['powershell','pwsh'] if shutil.which(name)))
        self.assertTrue(shells)
        for shell in shells:
            with self.subTest(shell=shell):
                result=subprocess.run([shell,'-NoProfile','-File',str(script),'-Workspace',str(workspace),'-Python',str(python),'-CheckOnly'],env=environment,capture_output=True,text=True,encoding='ascii',timeout=40)
                self.assertEqual(0,result.returncode,result.stderr)
                data=json.loads(result.stdout)
                self.assertEqual('available',data['status'])
                selected=Path(data['python_executable'])
                # Windows temp paths can use 8.3 aliases; identity must survive
                # normalization while the Chinese directory remains intact.
                self.assertTrue(selected.is_absolute());self.assertTrue(selected.samefile(python))
                self.assertIn(workspace.name,str(selected));self.assertNotIn('\ufffd',str(selected))
                initialized=subprocess.run([data['python_executable'],str(script.with_name('career.py')),'--workspace',str(workspace),'init'],env=environment,capture_output=True,text=True,encoding='utf-8',timeout=30)
                self.assertEqual(0,initialized.returncode,initialized.stderr)
        self.assertFalse((env.root(workspace)/'tools').exists())

    def selected_python_state(self,workspace,create=True):
        selected=next(env.local_python(workspace))
        if create:
            selected.parent.mkdir(parents=True);selected.write_bytes(b'FICTIONAL INVALID EXECUTABLE');selected.chmod(0o755)
        atomic(env.root(workspace)/'setup/environment.json',{'schema_version':1,'installation_policy':'auto','steps':{'python_packages':{'status':'available','python_executable':str(selected)}}})
        return selected

    def test_doctor_does_not_use_parent_packages_when_selected_runtime_is_broken_or_missing(self):
        for create in [True,False]:
            with self.subTest(create=create):
                workspace=self.workspace/str(create);workspace.mkdir()
                selected=self.selected_python_state(workspace,create)
                self.assertEqual(selected,env.configured_python(workspace))
                with patch.object(capabilities.importlib,'import_module',return_value=object()),patch.object(capabilities,'tool_path',return_value='fictional-compiler'),patch.object(capabilities,'pdf_smoke',side_effect=AssertionError('Must not compile with an invalid selected runtime')):
                    result=capabilities.report(workspace,check_pdf=True)
                self.assertEqual('runtime_required',result['setup']['status'])
                self.assertFalse(any(result['packages'].values()))
                self.assertFalse(result['features']['pdf_generation_and_qa']);self.assertFalse(result['features']['pdf_import'])
                self.assertTrue(result['features']['profile_text_docx_and_scoring'])
                self.assertIn('setup',result['next_actions'][0]['next_action'])

    def test_pdf_cli_blocks_broken_selected_runtime_before_package_changes_but_source_work_continues(self):
        person=make_workspace(self.workspace/'person');jobs.assess(person,assessment(person))
        self.selected_python_state(person.workspace)
        payload=person.root/'draft-input.json';atomic(payload,draft(person))
        before=(person.root/'profile.json').read_bytes()
        command=[sys.executable,str(PROJECT/'skills/career-assistant/scripts/career.py'),'--workspace',str(person.workspace),'render','demo-job','--input',str(payload)]
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(1,result.returncode);self.assertEqual('runtime_required',json.loads(result.stderr)['status'])
        self.assertFalse((person.root/'packages/demo-job').exists());self.assertEqual(before,(person.root/'profile.json').read_bytes())
        result=subprocess.run([*command,'--source-only'],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual('draft',json.loads(result.stdout)['status'])

    def test_selected_runtime_execution_denial_remains_a_permission_request(self):
        selected=self.selected_python_state(self.workspace)
        denial=env.SetupError('approval_required','Fictional denied runtime','Allow this exact runtime, then retry setup')
        with patch.object(capabilities,'probe_python',side_effect=denial),patch.object(capabilities.importlib,'import_module',return_value=object()):
            result=capabilities.report(self.workspace)
        self.assertEqual('approval_required',result['setup']['status'])
        self.assertFalse(any(result['packages'].values()));self.assertFalse(result['features']['pdf_import'])


if __name__=='__main__':unittest.main()
