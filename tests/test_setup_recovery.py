"""Setup consent, compatible runtimes and scoped dependency-write regressions."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from unittest.mock import patch
from fixtures import make_workspace
from storage import atomic
import environment as env
import capabilities
import career
import resume


class SetupRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.workspace=Path(self.temp.name)/'workspace';self.workspace.mkdir()
        self.workspace=self.workspace.resolve()
        self.good={'version':[3,13,1],'packages':{'pypdf':True,'fitz':True},'toml_parser':True}

    def ready_setup(self,**kwargs):
        with patch.object(env,'_install_packages',return_value={'status':'available','python_executable':sys.executable}),patch.object(env,'_install_tectonic',return_value={'status':'available','executable':'fixture'}),patch.object(env,'_warm_tex',return_value={'status':'available'}):
            return env.setup(self.workspace,**kwargs)

    def link(self,target,path):
        path.parent.mkdir(parents=True,exist_ok=True)
        if os.name=='nt':
            import _winapi
            _winapi.CreateJunction(str(target),str(path))
        else:path.symlink_to(target,target_is_directory=True)

    def node_files(self,folder):
        node=folder/('node.exe' if os.name=='nt' else 'bin/node')
        npm=folder/('node_modules/npm/bin/npm-cli.js' if os.name=='nt' else 'lib/node_modules/npm/bin/npm-cli.js')
        node.parent.mkdir(parents=True,exist_ok=True);node.write_text('Never executed fixture')
        npm.parent.mkdir(parents=True,exist_ok=True);npm.write_text('Never executed fixture')
        return node,npm

    def browser_module(self):
        modules=env.root(self.workspace)/'tools/browser/node_modules'
        module=modules/'@playwright/mcp';module.mkdir(parents=True)
        atomic(module/'package.json',{'version':'0.0.83','bin':{'playwright-mcp':'cli.js'},'engines':{'node':'>=18'}})
        (module/'cli.js').write_text('Never executed fixture')
        library=modules/'playwright';library.mkdir()
        atomic(library/'package.json',{'engines':{'node':'>=20'}})
        (library/'cli.js').write_text('Never executed fixture')
        return module,library

    def test_node18_is_not_reused_when_a_compatible_runtime_is_available(self):
        old,_=self.node_files(env.root(self.workspace)/'tools/node')
        compatible,npm=self.node_files(Path(self.temp.name)/'host-node')
        before=old.read_bytes()
        def command(args,**kwargs):return subprocess.CompletedProcess(args,0,'v18.20.8' if Path(args[0])==old else 'v22.12.0','')
        with patch.object(env.shutil,'which',side_effect=lambda name:str(compatible) if name=='node' else None),patch.object(env,'_command',side_effect=command),patch.object(env,'_fetch') as download:
            selected,cli=env._node(self.workspace,False)
        self.assertTrue(Path(selected).samefile(compatible));self.assertTrue(Path(cli).samefile(npm))
        self.assertEqual(before,old.read_bytes());download.assert_not_called()

    def test_node18_only_reports_compatible_runtime_needed_without_offline_install(self):
        self.node_files(env.root(self.workspace)/'tools/node')
        with patch.object(env.shutil,'which',return_value=None),patch.object(env,'_command',return_value=subprocess.CompletedProcess([],0,'v18.20.8','')),patch.object(env,'_fetch') as download:
            with self.assertRaises(env.SetupError) as caught:env._node(self.workspace,False)
        self.assertEqual('download_required',caught.exception.result['status'])
        self.assertIn('20+',caught.exception.result['reason']);download.assert_not_called()

    def test_downloaded_runtime_is_moved_to_its_stable_location_before_any_execution(self):
        old,_=self.node_files(env.root(self.workspace)/'tools/node')
        expected=env.root(self.workspace)/'tools/browser-node'
        archive=b'Fixture archive consumed by the extraction adapter; never executed'
        sha=hashlib.sha256(archive).hexdigest()
        def fetch(url,*args):
            if url.endswith('index.json'):return b'[{"version":"v22.12.0","lts":"Fixture"}]'
            if url.endswith('SHASUMS256.txt'):
                system={'Windows':'win','Darwin':'darwin','Linux':'linux'}[env.platform.system()]
                arch={'amd64':'x64','x86_64':'x64','arm64':'arm64','aarch64':'arm64'}[env.platform.machine().lower()]
                name='node-v22.12.0-'+system+'-'+arch+('.zip' if system=='win' else '.tar.gz')
                return (sha+'  '+name+'\n').encode()
            return archive
        def extract(archive,directory,**kwargs):self.node_files(Path(directory))
        def command(args,**kwargs):
            if Path(args[0])==old:return subprocess.CompletedProcess(args,0,'v18.20.8','')
            self.assertTrue(Path(args[0]).is_relative_to(expected));self.assertTrue(Path(args[0]).is_file())
            return subprocess.CompletedProcess(args,0,'v22.12.0','')
        with patch.object(env.shutil,'which',return_value=None),patch.object(env,'_fetch',side_effect=fetch),patch.object(env,'_unpack',side_effect=extract),patch.object(env,'_command',side_effect=command):
            node,npm=env._node(self.workspace,True)
        self.assertTrue(Path(node).is_relative_to(expected));self.assertTrue(Path(npm).is_file())

    def test_failed_mcp_cli_never_registers_a_server_even_if_browser_library_exists(self):
        module,_=self.browser_module()
        def command(args,**kwargs):
            if len(args)==2:return subprocess.CompletedProcess(args,0,'v22.12.0','')
            raise env.SetupError('retryable_error','Fixture CLI cannot start','Repair the compatible runtime')
        with patch.object(env,'_node',return_value=('fixture-node','fixture-npm')),patch.object(env,'_command',side_effect=command),patch.object(env,'_register_browser') as register:
            with self.assertRaises(env.SetupError):env._install_browser(self.workspace,'codex',False)
        register.assert_not_called();self.assertFalse((self.workspace/'.codex/config.toml').exists())

    def test_native_runtime_crash_retries_once_with_local_runtime_excluding_failed_binary(self):
        failure=env.SetupError('retryable_error','Fixture native crash','Use compatible runtime',['fixture-node','cli.js'])
        failure.result['exit_code']=0xC0000005
        with patch.object(env,'_prepare_browser',side_effect=[failure,{'status':'host_reload_required'}]) as prepare,patch.object(env,'_node',return_value=('local-lts','local-npm')) as runtime:
            result=env._install_browser(self.workspace,'codex',True)
        runtime.assert_called_once_with(self.workspace,True,exclude=('fixture-node',),local_only=True)
        self.assertEqual(2,prepare.call_count);self.assertEqual('host_reload_required',result['status'])

    def test_permission_denial_never_retries_with_another_browser_runtime(self):
        failure=env.SetupError('approval_required','Fixture policy denial','Allow this exact execution',['fixture-node'])
        failure.result['exit_code']=0xC0000005
        with patch.object(env,'_prepare_browser',side_effect=failure) as prepare,patch.object(env,'_node') as runtime:
            with self.assertRaises(env.SetupError):env._install_browser(self.workspace,'codex',True)
        self.assertEqual(1,prepare.call_count);runtime.assert_not_called()

    def test_browser_deferral_survives_inspection_missing_capability_and_existing_tool(self):
        with patch.object(env,'_install_browser') as install:
            first=self.ready_setup(browser='defer',search='defer')
            for browser in ['inspect','missing','existing','missing']:
                current=self.ready_setup(browser=browser,search='inspect')
                self.assertEqual('deferred',current['component_policies']['browser'])
                self.assertEqual('deferred',current['steps']['search']['status'])
                self.assertEqual('available' if browser=='existing' else 'deferred',current['steps']['browser']['status'])
        self.assertEqual('deferred',first['steps']['browser']['status']);install.assert_not_called()

    def test_legacy_browser_deferral_is_preserved_until_explicit_component_resume(self):
        atomic(env.root(self.workspace)/'setup/environment.json',{'schema_version':1,'installation_policy':'auto','steps':{'browser':{'status':'deferred'}}})
        first=self.ready_setup(browser='missing',search='existing')
        self.assertEqual('deferred',first['steps']['browser']['status'])
        with patch.object(env,'_install_browser',return_value={'status':'host_reload_required'}) as install:
            resumed=self.ready_setup(browser='missing',search='existing',resume_browser=True)
        self.assertEqual('auto',resumed['component_policies']['browser']);install.assert_called_once_with(self.workspace,'codex',True)

    def test_browser_only_resume_keeps_pdf_and_search_deferred(self):
        self.ready_setup(defer=True,browser='defer',search='defer')
        calls=[]
        with patch.object(env,'_install_packages',side_effect=lambda w,d:(calls.append(d) or {'status':'available','python_executable':sys.executable})),patch.object(env,'_install_tectonic',return_value={'status':'available','executable':'fixture'}),patch.object(env,'_warm_tex',return_value={'status':'available'}),patch.object(env,'_install_browser',return_value={'status':'host_reload_required'}) as install:
            result=env.setup(self.workspace,browser='missing',search='missing',resume_browser=True)
        self.assertEqual([False],calls);install.assert_called_once_with(self.workspace,'codex',True)
        self.assertEqual('deferred',result['installation_policy']);self.assertEqual('deferred',result['steps']['search']['status'])
        resumed=self.ready_setup(browser='existing',search='existing',resume_search=True)
        self.assertEqual('available',resumed['steps']['search']['status'])

    def test_invalid_component_policy_never_starts_an_installer(self):
        path=env.root(self.workspace)/'setup/environment.json'
        for value in [None,[],{'browser':[]},{'browser':True},{'browser':'unknown'},{'unrecognized':'auto'}]:
            with self.subTest(value=value):
                atomic(path,{'schema_version':1,'installation_policy':'auto','steps':{},'component_policies':value})
                before=path.read_bytes()
                with patch.object(env,'_install_packages') as install:
                    result=env.setup(self.workspace)
                self.assertEqual('configuration_review_required',result['status']);self.assertEqual(before,path.read_bytes());install.assert_not_called()

    def test_linked_tools_are_rejected_before_download_or_directory_creation(self):
        outside=Path(self.temp.name)/'outside';outside.mkdir()
        self.link(outside,env.root(self.workspace)/'tools')
        with patch.object(env,'tool_path',return_value=None),patch.object(env,'_fetch') as download:
            with self.assertRaises(env.SetupError) as caught:env._install_tectonic(self.workspace)
        self.assertEqual('configuration_review_required',caught.exception.result['status'])
        self.assertEqual([],list(outside.iterdir()));download.assert_not_called()

    def test_explicit_workspace_alias_is_normalized_without_allowing_external_write_targets(self):
        actual=Path(self.temp.name)/'actual-workspace';actual.mkdir()
        alias=self.workspace/'selected-workspace';self.link(actual,alias)
        destination=env._install_path(alias,alias/'.career-assistant/tools/cache')
        self.assertEqual((actual/'.career-assistant/tools/cache').resolve(),destination)
        with self.assertRaises(env.SetupError):env._install_path(alias,self.workspace/'unrelated')

    def test_incomplete_linked_venv_gets_a_local_fallback_without_external_pip(self):
        outside=Path(self.temp.name)/'outside';outside.mkdir()
        old=outside/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        old.parent.mkdir();old.write_text('Never executed fixture')
        self.link(outside,self.workspace/'.venv')
        selected=list(env.local_python(self.workspace))[1];installed=False;commands=[]
        def probe(executable):
            folder=Path(executable).parent.parent
            return {**self.good,'packages':{'pypdf':installed,'fitz':installed},'prefix':str(folder.resolve()),'install_paths':{k:str(folder.resolve()) for k in ['purelib','platlib','scripts','data']}}
        def create(folder):selected.parent.mkdir(parents=True);selected.write_text('Never executed fixture')
        def command(args,**kwargs):
            nonlocal installed
            commands.append(list(map(str,args)))
            if 'install' in args:installed=True
            return subprocess.CompletedProcess(args,0,'','')
        with patch.object(env,'probe_python',side_effect=probe),patch.object(env.venv.EnvBuilder,'create',side_effect=create),patch.object(env,'_command',side_effect=command):
            result=env._install_packages(self.workspace)
        self.assertEqual(str(selected),result['python_executable'])
        self.assertTrue(all(c[0]==str(selected) for c in commands));self.assertEqual('Never executed fixture',old.read_text())
        self.assertEqual([old],sorted(p for p in outside.rglob('*') if p.is_file()))

    def test_already_selected_linked_runtime_does_not_delegate_recursively(self):
        outside=Path(self.temp.name)/'shared';outside.mkdir()
        self.link(outside,self.workspace/'.venv')
        selected=next(env.local_python(self.workspace))
        atomic(env.root(self.workspace)/'setup/environment.json',{'schema_version':1,'installation_policy':'auto','steps':{'python_packages':{'status':'available','python_executable':str(selected)}}})
        payload=self.workspace/'draft.json';payload.write_text('{}')
        with patch.object(sys,'prefix',str(outside)),patch.object(env,'probe_python') as probe,patch.object(career.subprocess,'run') as delegate,patch.object(resume,'render',return_value={'reused':True}) as render:
            result=career.main(['--workspace',str(self.workspace),'render','fixture','--input',str(payload)])
        self.assertEqual({'reused':True},result);render.assert_called_once();probe.assert_not_called();delegate.assert_not_called()

    def test_executable_alias_with_same_global_prefix_does_not_delegate_recursively(self):
        selected=next(env.local_python(self.workspace))
        atomic(env.root(self.workspace)/'setup/environment.json',{'schema_version':1,'installation_policy':'auto','steps':{'python_packages':{'status':'available','python_executable':str(selected)}}})
        payload=self.workspace/'draft.json';payload.write_text('{}')
        with patch.object(env,'probe_python',return_value={**self.good,'prefix':sys.prefix}) as probe,patch.object(career.subprocess,'run') as delegate,patch.object(resume,'render',return_value={'reused':True}) as render:
            result=career.main(['--workspace',str(self.workspace),'render','fixture','--input',str(payload)])
        self.assertEqual({'reused':True},result);render.assert_called_once();delegate.assert_not_called();probe.assert_called_once_with(selected)

    def test_global_prefix_cannot_be_treated_as_a_writable_local_venv(self):
        executable=next(env.local_python(self.workspace))
        executable.parent.mkdir(parents=True);executable.write_text('Never executed fixture')
        info={**self.good,'prefix':sys.prefix,'install_paths':{k:sys.prefix for k in ['purelib','platlib','scripts','data']}}
        with self.assertRaises(env.SetupError):env._verify_venv_writes(self.workspace,executable,info)

    def test_linked_browser_install_cache_engine_and_profile_targets_are_rejected(self):
        for index,relative in enumerate(['setup/npm-cache','browser/engines','browser/profile']):
            with self.subTest(relative=relative):
                workspace=self.workspace/str(index);workspace.mkdir()
                original=self.workspace;self.workspace=workspace
                try:
                    if relative!='setup/npm-cache':self.browser_module()
                    outside=Path(self.temp.name)/('outside-'+str(index));outside.mkdir()
                    self.link(outside,env.root(workspace)/relative)
                    with patch.object(env,'_node',return_value=('fixture-node','fixture-npm')),patch.object(env,'_command') as command:
                        with self.assertRaises(env.SetupError) as caught:env._install_browser(workspace,'codex',True)
                    self.assertEqual('configuration_review_required',caught.exception.result['status']);command.assert_not_called();self.assertEqual([],list(outside.iterdir()))
                finally:self.workspace=original

    @unittest.skipIf(os.name=='nt','Standard POSIX venv interpreter links')
    def test_standard_venv_python_links_and_internal_directory_aliases_are_allowed(self):
        folder=self.workspace/'.venv';venv.EnvBuilder(with_pip=False).create(folder)
        executable=folder/'bin/python';info=env.probe_python(executable)
        (folder/'inside-alias').symlink_to(folder/'lib',target_is_directory=True)
        env._install_tree(self.workspace,folder,python_runtime=True)
        env._verify_venv_writes(self.workspace,executable,info)

    def test_recovery_rediscovers_retained_tex_cache_before_requesting_downloads(self):
        cache=env.root(self.workspace)/'tools/tex-cache';cache.mkdir(parents=True);(cache/'resource.fixture').write_text('Public cached resource marker')
        state=env.root(self.workspace)/'setup/environment.json';state.parent.mkdir();original=b'{broken'
        state.write_bytes(original)
        result=env.recover_setup(self.workspace,'defer','Fictional owner explicitly continues deferral')
        self.assertEqual(original,Path(result['backup_path']).read_bytes())
        calls=[]
        def command(args,**kwargs):
            calls.append(list(map(str,args)))
            self.assertIn('--only-cached',args);self.assertEqual(str(cache),kwargs['env']['TECTONIC_CACHE_DIR'])
            Path(args[-1]).with_suffix('.pdf').write_bytes(b'Anonymous fixture probe; not PDF acceptance')
            return subprocess.CompletedProcess(args,0,'','')
        with patch.object(env,'_command',side_effect=command),patch.dict(os.environ,{'TECTONIC_CACHE_DIR':str(self.workspace/'empty-global-cache')}):
            verified=env._warm_tex(self.workspace,'fixture',False)
        self.assertEqual('available',verified['status']);self.assertEqual('workspace',verified['cache_scope']);self.assertEqual(1,len(calls))

    def test_doctor_does_not_claim_ready_when_private_tex_cache_redirects_outside(self):
        outside=Path(self.temp.name)/'outside-cache';outside.mkdir()
        self.link(outside,env.root(self.workspace)/'tools/tex-cache')
        with patch.object(capabilities.importlib,'import_module',return_value=object()),patch.object(capabilities,'tool_path',return_value='fixture'):
            report=capabilities.report(self.workspace,check_pdf=True)
        self.assertEqual('configuration_review_required',report['setup']['status']);self.assertFalse(report['features']['pdf_generation_and_qa'])
        self.assertEqual([],list(outside.iterdir()))


if __name__=='__main__':unittest.main()
