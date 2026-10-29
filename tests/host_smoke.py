"""Real conversations from an EMPTY fictional workspace; disk evidence, not exit codes.

Every turn starts a new session to test recovery from saved local state. Logs are
private; no browsers, real accounts or applications. Exit 2 = blocked/unverified.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

PROJECT = Path(__file__).resolve().parents[1]
BOUNDARY = ('这是虚构用户的隔离验收，职业资料只读写当前工作区，不访问工作区外的用户资料、浏览器、账号或网络；可使用本机已有程序、依赖和编译缓存，'
            '本次宿主对话仅复用现有依赖，不下载或安装；环境步骤运行 setup --no-downloads --browser defer --search defer，实际缺依赖安装由独立冷启动验收覆盖。'
            '不投递、不创建仓库、不提交代码、不修改程序或共享skill源文件。不要委派子代理。使用本项目职业助手及其本地脚本。')
PROMPTS = [
    ('initialize', '帮我初始化信息。请开始正常的分步建档，保存进度，最多问三个问题，然后等待。'),
    ('facts', '我没有简历。以下是我确认的虚构资料：我叫 Taylor Brook，邮箱 '
     'taylor@example.invalid，位于 London, UK。2023年1月至2025年12月在 Fictional '
     'Harbor Software 做 Software Developer，亲自开发 TypeScript API 并编写自动化测试。'
     '2022年在 Fictional North College 取得 BSc Computer Science，本科学习时间是2018至2022年。'
     '我有英国工作许可，不需要雇主担保。请保存原话与确认事实，完成已有材料的步骤；'
     '不要预填求职偏好，问下一步最多三个问题。'),
    ('resume', '继续上次的初始化。先从磁盘恢复，告诉我已保存的姓名、最近工作和下一步。'
     '这轮没有新事实或修改，请不要重写已有事实，也不要让我重新提供已经保存的内容。'),
    ('roles', '我的目标是 Software Engineer，方向 ID 使用 software，优先 TypeScript API 和自动化测试。'
     '地区 London, UK，远程或混合办公，永久全职，其他偏好暂时未知。Projects 关闭。'
     '我选择每份申请最终提交前确认，这不是投递授权。请保存这些偏好，生成两个宿主的个人岗位 '
     'resume-tailor skills，并保存已完成的建档步骤。浏览器配置暂缓，下一步我提供完整 JD。'),
    ('invoke', '请调用 career-resume-software 个人 skill，读取其完整指令、私人 routes/software.md 文档和岗位配置，'
     '为下面完整虚构 JD 评分，用模板生成简历源文件（只做 source-only，不编译或声称PDF已就绪）。'
     '岗位 ID 为 host-trial。Fictional Harbor Labs, Software Engineer, London UK, '
     'permanent full-time, hybrid. Full JD: Build TypeScript APIs, write automated tests, '
     'and communicate implementation decisions with teammates. Required: practical TypeScript '
     'API development, automated testing experience, a computer science degree or equivalent '
     'experience, and existing UK work authorization without sponsorship. Salary not specified. '
     'Source URL https://example.invalid/jobs/host-trial . Do not apply. '
     '未知要求如实标记。Projects保持关闭，生成后停止。'),
]


def read(root, name, default=None):
    p = root / '.career-assistant' / name
    return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else default


def snapshot(root):
    return {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ['.career-assistant', '.agents', '.claude']
            for p in (root / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}


def checks(root, stage, before):
    profile = read(root, 'profile.json', {})
    prefs = read(root, 'preferences.json', {})
    progress = read(root, 'onboarding.json', {})
    facts = profile.get('facts', {})
    result = {'profile_exists': bool(profile), 'tracker_empty': read(root, 'tracker.json', {}).get('record_count') == 0}
    if stage == 'initialize':
        result.update(empty_profile=not facts, environment_saved='environment' in progress.get('completed', []), no_default_routes=not (root/'.career-assistant/routes').exists(), dependency_setup_saved=(root/'.career-assistant/setup/environment.json').is_file())
    elif stage == 'facts':
        text = ' '.join(f.get('text', '') for f in facts.values())
        sources = read(root, 'sources.json', {}).get('sources', {})
        result.update(name_saved='Taylor Brook' in text, work_saved='TypeScript' in text,
                      education_saved='Fictional North College' in text,
                      source_backed=bool(facts) and all(f.get('source_ids') and all(s in sources for s in f['source_ids']) for f in facts.values()),
                      facts_checkpoint='facts' in progress.get('completed', []), no_targets_assumed=not prefs.get('targets'))
    elif stage == 'resume':
        for file in ['profile.json', 'onboarding.json']:
            key = '.career-assistant/'+file
            result[file+'_preserved'] = before.get(key) == snapshot(root).get(key)
    elif stage == 'roles':
        result.update(role_created=bool(read(root, 'roles/software.json')),
                      personal_route=(root/'.career-assistant/routes/software.md').is_file(),
                      codex_skill=(root/'.agents/skills/career-resume-software/SKILL.md').is_file(),
                      claude_skill=(root/'.claude/skills/career-resume-software/SKILL.md').is_file(),
                      policy=prefs.get('submission_policy') == 'per-application', projects_off=prefs.get('include_projects') is False,
                      automation_checkpoint='automation' in progress.get('completed', []),
                      no_submission_grant=not read(root, 'grants.json', {}).get('grants'))
    else:
        tex = root/'.career-assistant/packages/host-trial/resume.tex'
        result.update(assessment=bool(read(root, 'jobs/host-trial.json')), source_rendered=tex.is_file(),
                      projects_absent=tex.is_file() and '\\section{Projects}' not in tex.read_text(encoding='utf-8'),
                      remains_draft=read(root, 'packages/host-trial/validation.json', {}).get('status') == 'draft',
                      trial_not_claimed='trial' not in progress.get('completed', []))
    return result


def command(host, root, result_dir, stage, executable=None, sandbox=None):
    if executable:
        executable = shutil.which(str(executable))
    else:
        # Windows may have an older npm .cmd/.ps1 ahead of the app's native CLI.
        executable = (shutil.which('codex.exe') if host == 'codex' and os.name == 'nt' else None) or shutil.which(host)
    if not executable:
        raise FileNotFoundError(f'{host} executable unavailable')
    if host == 'codex':
        # Keep the host's model and native Windows sandbox setup; ignoring the
        # user config can silently downgrade older Windows clients to read-only.
        args = [executable, 'exec', '--skip-git-repo-check', '--ephemeral']
        if sandbox:
            args += ['--sandbox', sandbox]
        return args + ['-C', str(root), '--json', '-o', str(result_dir/(stage+'-answer.txt')), '-']
    return [executable, '-p', '--no-session-persistence', '--permission-mode', 'acceptEdits',
            '--allowedTools', 'Read', 'Glob', 'Grep', 'Write', 'Edit', 'Bash(python *)',
            '--tools', 'Read,Glob,Grep,Write,Edit,Bash,Skill', '--strict-mcp-config',
            '--mcp-config', '{"mcpServers":{}}', '--output-format', 'stream-json', '--verbose']


def prepare_workspace(root, host, preinstall=False):
    """Copy only the public download; default first use has no installed skills."""
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError('Host acceptance requires a new empty workspace')
    spec = importlib.util.spec_from_file_location('career_host_release', PROJECT/'release.py')
    release = importlib.util.module_from_spec(spec); spec.loader.exec_module(release)
    for source in [*release.public_files(), PROJECT/'release_manifest.json']:
        target = root/source.relative_to(PROJECT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if preinstall:
        subprocess.run([sys.executable, str(root/'install.py'), '--host', host], cwd=root, check=True, capture_output=True)
    return {'profile_exists': (root/'.career-assistant').exists(),
            'codex_skills_exist': (root/'.agents/skills').exists(),
            'claude_skills_exist': (root/'.claude/skills').exists(), 'git_exists': (root/'.git').exists()}


def run(host, results, timeout, executable=None, sandbox=None, preinstall=False, workspace_parent=None):
    # Keep source-only first use outside an ancestor repo's discovered project skills.
    workspace_parent = Path(workspace_parent or Path(tempfile.gettempdir())/'career-assistant-host-tests').resolve()
    workspace_parent.mkdir(parents=True, exist_ok=True)
    # On Python 3.13/Windows, mkdtemp's owner-only ACL can leave files created
    # by the dedicated sandbox account unreadable to the external verifier.
    # Inherit the selected parent's ACLs; fixtures stay local and logs stay ignored.
    root = workspace_parent/('career-host-'+host+'-'+uuid.uuid4().hex[:12])
    root.mkdir()
    result_dir = results.resolve()/root.name
    result_dir.mkdir(parents=True)
    initial = prepare_workspace(root, host, preinstall)
    result = {'host': host, 'isolated_workspace': str(root), 'results': str(result_dir), 'stages': [],
              'initial_state': initial, 'preinstalled': preinstall,
              'acceptance': 'unverified', 'permissions': sandbox or 'existing user configuration', 'manual_transcript_review_required': True}
    for stage, prompt in PROMPTS:
        before = snapshot(root)
        (result_dir/(stage+'-prompt.txt')).write_text(BOUNDARY+prompt, encoding='utf-8')
        row = {'stage': stage}
        try:
            completed = subprocess.run(command(host, root, result_dir, stage, executable, sandbox), input=BOUNDARY+prompt, cwd=root,
                                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
            for label, text in [('stdout', completed.stdout), ('stderr', completed.stderr)]:
                (result_dir/(stage+'-'+label+'.txt')).write_text(text, encoding='utf-8')
            row.update(exit_code=completed.returncode, checks=checks(root, stage, before))
            row['passed'] = completed.returncode == 0 and all(row['checks'].values())
            combined = completed.stdout + completed.stderr
            # Optional MCP startup warnings are not a host/model login failure.
            if completed.returncode != 0 and ('OAuth access token is invalid' in combined or 'Failed to authenticate.' in completed.stdout):
                row['blocker'] = 'Host authentication failed; sign in locally and rerun.'
        except (subprocess.TimeoutExpired, OSError) as exc:
            row.update(passed=False, blocker=type(exc).__name__)
            if isinstance(exc, subprocess.TimeoutExpired):
                for label, value in [('stdout', exc.stdout), ('stderr', exc.stderr)]:
                    text = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
                    (result_dir/(stage+'-'+label+'.txt')).write_text(text, encoding='utf-8')
        after = snapshot(root)
        row['changed_files'] = [name for name, value in after.items() if before.get(name) != value]
        result['stages'].append(row)
        (result_dir/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({'host': host, **row}, ensure_ascii=False), flush=True)
        if not row['passed']:
            break
    result['acceptance'] = 'disk-checks-passed-needs-transcript-review' if len(result['stages']) == len(PROMPTS) and all(s['passed'] for s in result['stages']) else 'blocked-or-failed'
    (result_dir/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'acceptance': result['acceptance'], 'results': str(result_dir)}, indent=2), flush=True)
    return 0 if result['acceptance'].startswith('disk-checks-passed') else 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('host', choices=['codex', 'claude'])
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--timeout', type=int, default=240, help='Maximum seconds for each host turn')
    ap.add_argument('--executable', type=Path, help='Use a specific installed host CLI when PATH selects an older copy')
    ap.add_argument('--sandbox', choices=['read-only','workspace-write','danger-full-access'], help='Optional Codex sandbox override; default retains the user-selected permissions')
    ap.add_argument('--preinstall-skill', action='store_true', help='Additionally exercise an installed skill; default tests the uninstalled public download')
    ap.add_argument('--workspace-parent', type=Path, help='Optional isolated workspace parent; default is outside the source repo in the local temp directory')
    args = ap.parse_args()
    sys.exit(run(args.host, args.results, args.timeout, args.executable, args.sandbox, args.preinstall_skill, args.workspace_parent))
