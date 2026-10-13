"""Shared checks for private role context and generated host skills."""
from storage import digest, inside, load, slug

HOST_FOLDERS = {'codex': '.agents', 'claude': '.claude'}


def skill_path(role_id, host):
    return f'{HOST_FOLDERS[host]}/skills/career-resume-{slug(role_id)}/SKILL.md'


def matches_target(role, target):
    labels = [target.get('id', ''), target.get('title', '')] if isinstance(target, dict) else [target]
    return any(isinstance(label, str) and label.strip().casefold() in {role['id'].casefold(), role['title'].casefold()} for label in labels)


def context_digest(role, route_hash):
    # Installation progress and timestamps do not change writing/scoring context.
    configuration = {k: v for k, v in role.items() if k not in {'created_at', 'generation'}}
    return digest({'configuration': configuration, 'route_content_sha256': route_hash})


def context_hash(store, role_id):
    rid = slug(role_id)
    role = store.read(f'roles/{rid}.json')
    if role.get('id') != rid or role.get('route_path') != f'routes/{rid}.md':
        raise ValueError('Refresh the role configuration and its personal route first')
    route = inside(store.root, store.root / role['route_path'])
    try:
        route_hash = digest(route.read_bytes())
    except OSError:
        raise ValueError('Personal route is missing or unreadable; restore or refresh it first') from None
    return context_digest(role, route_hash)


def problem(store, role):
    """Return a recoverable issue; never accept a partially installed role."""
    try:
        current = context_hash(store, role['id'])
        route = store.root / role['route_path']
        if role.get('route_sha256') != digest(route.read_bytes()):
            return 'Personal route changed; refresh this role from its confirmed configuration'
        generation = role.get('generation', {})
        hosts = generation.get('hosts', [])
        if not hosts or any(h not in HOST_FOLDERS for h in hosts):
            return 'Legacy role has no installation record; refresh it with role-create'
        if generation.get('context_hash') != current:
            return 'Role configuration changed; refresh its personal route and skills'
        if generation.get('status') != 'ready':
            return f"Personal skill generation is pending; resolve the reported write problem and use role-retry {role['id']}"
        skills = generation.get('skills', {})
        for host in hosts:
            expected = skills.get(host, {})
            name = skill_path(role['id'], host)
            path = inside(store.workspace, store.workspace / name)
            if expected.get('path') != name or not path.is_file() or expected.get('sha256') != digest(path.read_bytes()):
                return f"{host} personal skill is missing or changed; use role-retry {role['id']}"
    except (ValueError, KeyError, OSError) as exc:
        return f'Role configuration or personal route needs repair: {type(exc).__name__}'
    return None


def selected_issues(store):
    roles = [load(path) for path in (store.root / 'roles').glob('*.json')]
    issues = []
    for target in store.read('preferences.json')['targets']:
        matching = [role for role in roles if matches_target(role, target)]
        failures = [problem(store, role) for role in matching]
        if not matching or all(failures):
            issues.append({'target': target, 'detail': failures[0] if failures else 'Create the selected role, personal route and personal skills first'})
    return issues


def require_selected(store):
    issues = selected_issues(store)
    if not store.read('preferences.json')['targets'] or issues:
        detail = issues[0]['detail'] if issues else 'Choose at least one target direction first'
        raise ValueError('Generate or refresh each selected role, personal route and all requested personal skills before completing this step. ' + detail)
