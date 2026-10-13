from __future__ import annotations
import re
import shutil
import subprocess
from pathlib import Path
from storage import SCHEMA, atomic, digest, now, slug
from jobs import fresh

ASSETS = Path(__file__).resolve().parent.parent / 'assets'

def escape(text):
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    text = str(text).replace('\n', ' ').replace('\r', ' ')
    return ''.join(replacements.get(c, c) for c in text)

def render(store, job_id, draft, compile_pdf=True):
    job_id = slug(job_id)
    assessment = store.read(f'jobs/{job_id}.json')
    fresh(store, assessment)
    facts = store.read('profile.json')['facts']
    prefs = store.read('preferences.json')
    if not draft.get('evidence_review'):
        raise ValueError('Review every draft claim against its cited facts and record evidence_review')
    used = set()
    plain = []

    def claim(obj):
        if not isinstance(obj, dict) or not obj.get('text') or not obj.get('evidence_ids'):
            raise ValueError('Every resume claim needs text and evidence_ids')
        for fid in obj['evidence_ids']:
            if fid not in facts or facts[fid]['status'] not in {'documented', 'user_confirmed'}:
                raise ValueError('Unconfirmed/estimated facts cannot silently become resume claims: ' + fid)
            used.add(fid)
        plain.append(obj['text'])
        return escape(obj['text'])

    def entries(rows):
        parts = [r'\resumeSubHeadingListStart']
        for e in rows:
            parts.append(r'\resumeSubheading{' + claim(e['organization']) + '}{' + claim(e['dates']) + '}{' + claim(e['title']) + '}{' + (claim(e['location']) if e.get('location') else '') + '}')
            if e.get('bullets'):
                parts.append(r'\resumeItemListStart')
                parts += [r'\resumeItem{' + claim(b) + '}' for b in e['bullets']]
                parts.append(r'\resumeItemListEnd')
        parts.append(r'\resumeSubHeadingListEnd')
        return '\n'.join(parts)

    header = draft['header']
    parts = [r'\begin{center}', r'{\Huge \scshape ' + claim(header['name']) + r'} \\ \vspace{1pt}']
    if header.get('headline'):
        parts.append(r'\textbf{' + claim(header['headline']) + r'} \\ \vspace{2pt}')
    parts += [r'\small ' + r' $\cdot$ '.join(claim(c) for c in header.get('contacts', [])), r'\end{center}', r'\vspace{-14pt}']
    header_tex = '\n'.join(parts)
    summary = claim(draft['summary'])
    skill_lines = [r'\textbf{' + escape(g['label']) + ':} ' + ', '.join(claim(i) for i in g['items']) for g in draft['skills']]
    if not draft.get('experience') or not draft.get('education'):
        raise ValueError('Work Experience and Education need source-backed entries; ask for missing information')
    exp = entries(draft['experience'])
    projects_enabled = draft.get('include_projects', prefs['include_projects'])
    if type(projects_enabled) is not bool:
        raise ValueError('include_projects must be boolean')
    if projects_enabled and not prefs['include_projects'] and not draft.get('project_section_request'):
        raise ValueError('Adding Projects requires the user request; having projects alone does not enable the section')
    if draft.get('projects') and not projects_enabled:
        raise ValueError('Projects are off by default; omit them or record the user request')
    projects = '\\section{Projects}\n' + entries(draft['projects']) if projects_enabled and draft.get('projects') else ''
    education = entries(draft['education'])
    template = (ASSETS / 'resume-template.tex').read_text(encoding='utf-8')
    for key, value in {'HEADER': header_tex, 'SUMMARY': summary, 'SKILLS': r' \\'.join(skill_lines), 'EXPERIENCE': exp, 'PROJECTS': projects, 'EDUCATION': education}.items():
        template = template.replace('@@' + key + '@@', value)
    if re.search(r'@@[A-Z]+@@', template):
        raise ValueError('Unfilled layout slot')
    package = store.root / 'packages' / job_id
    with store.lock():
        package.mkdir(parents=True, exist_ok=True)
        (package / 'resume.tex').write_text(template, encoding='utf-8')
        atomic(package / 'draft.json', draft)
        (package / 'JD_snapshot.md').write_text(f"# {assessment['job']['company']} — {assessment['job']['title']}\n\nSource: {assessment['job']['url']}\nCaptured: {assessment['job']['captured_at']}\n\n{assessment['job']['text']}\n", encoding='utf-8')
        text = ' '.join(plain).casefold()
        coverage = []
        for requirement in assessment['requirements']:
            terms = requirement.get('keywords', [])
            present = bool(terms) and all(t.casefold() in text for t in terms)
            coverage.append({'requirement': requirement['requirement'], 'keywords': terms, 'present': present, 'weight': 3 if requirement.get('must_have') else 1})
        measurable = [r for r in coverage if r['keywords']]
        score = round(100 * sum(r['weight'] for r in measurable if r['present']) / sum(r['weight'] for r in measurable)) if measurable else None
        report = {'schema_version': SCHEMA, 'rubric_version': assessment['rubric_version'], 'job_fit': assessment['fit_score'], 'eligibility': assessment['eligibility_result'], 'preferences': assessment['preference_score'], 'keyword_coverage': score, 'unmeasured_requirements': len(coverage) - len(measurable), 'coverage': coverage, 'gaps': assessment['gaps'], 'fact_ids': sorted(used)}
        store.write(f'packages/{job_id}/match-report.json', report)
        (package / 'ATS_Match_Report.md').write_text('# Match report (estimated)\n\nThese are internal rubric scores, not employer ATS scores or hiring probabilities.\n\n' + f"Eligibility: {report['eligibility']}\n\nJob fit: {report['job_fit']}/100\n\nPreference match: {report['preferences']}\n\nExact keyword coverage: {score}; unmeasured requirements: {report['unmeasured_requirements']}\n\n" + '\n'.join(f"- {r['requirement']}: {'present' if r['present'] else 'not present / not measurable'}" for r in coverage) + '\n\nGaps:\n' + '\n'.join('- ' + g for g in assessment['gaps']) + '\n', encoding='utf-8')
        validation = {'schema_version': SCHEMA, 'status': 'draft', 'profile_hash': assessment['profile_hash'], 'assessment_hash': digest(assessment), 'source_sha256': digest((package / 'resume.tex').read_bytes()), 'generated_at': now(), 'projects_included': bool(projects)}
        store.write(f'packages/{job_id}/validation.json', validation)
        # Remove stale output from a prior draft before invoking any compiler.
        for stale in ['resume.pdf', 'resume.txt', 'resume.log']:
            (package / stale).unlink(missing_ok=True)
        if not compile_pdf:
            return {'package': str(package), 'status': 'draft'}
        compiler = shutil.which('tectonic')
        if not compiler:
            raise ValueError('Tectonic is missing. Source saved as draft; follow references/setup.md')
        try:
            import fitz
        except (ImportError, OSError):
            raise ValueError('PDF QA needs PyMuPDF in this Python environment. Source saved as draft; install PDF dependencies in the workspace .venv before compiling.') from None
        try:
            p = subprocess.run([compiler, '--keep-logs', '--outdir', str(package), str(package / 'resume.tex')], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
        except subprocess.TimeoutExpired:
            raise ValueError('PDF compilation timed out. Source saved as draft; check Tectonic and first-run TeX bundle network/cache access before retrying.') from None
        (package / 'compile-output.txt').write_text(p.stdout + p.stderr, encoding='utf-8')
        if p.returncode or not (package / 'resume.pdf').exists() or 'Missing character:' in p.stdout + p.stderr:
            raise ValueError('Compilation failed or glyphs are missing; inspect compile-output.txt. First-run TeX downloads may need network access. The package remains draft.')
        doc = fitz.open(package / 'resume.pdf')
        extracted = '\n'.join(page.get_text() for page in doc)
        pages = len(doc)
        bounds_ok = all(0 <= b[0] <= b[2] <= page.rect.width + 1 and 0 <= b[1] <= b[3] <= page.rect.height + 1 for page in doc for b in page.get_text('blocks') if b[4].strip())
        for i, page in enumerate(doc):
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(package / f'preview-{i+1}.png')
        doc.close()
        (package / 'resume.txt').write_text(extracted, encoding='utf-8')
        sections_ok = all(s in extracted for s in ['Summary', 'Skills', 'Work Experience', 'Education'])
        validation.update({'pages': pages, 'bounds_ok': bounds_ok, 'sections_ok': sections_ok, 'extractable_characters': len(extracted.strip()), 'pdf_sha256': digest((package / 'resume.pdf').read_bytes()), 'status': 'needs-visual-review' if pages == 1 and bounds_ok and sections_ok and len(extracted.strip()) > 100 else 'failed'})
        store.write(f'packages/{job_id}/validation.json', validation)
        if validation['status'] == 'failed':
            raise ValueError('PDF QA failed (page count, bounds, sections or extraction). Trim content; do not shrink the layout.')
    return {'package': str(package), **validation}

def visual_review(store, job_id, payload):
    with store.lock():
        validation = store.read(f'packages/{slug(job_id)}/validation.json')
        package = store.root / 'packages' / job_id
        if validation['status'] not in {'needs-visual-review', 'ready'}:
            raise ValueError('Automated PDF QA must pass first')
        assessment = store.read(f'jobs/{job_id}.json')
        fresh(store, assessment)
        if validation['assessment_hash'] != digest(assessment) or validation['pdf_sha256'] != digest((package / 'resume.pdf').read_bytes()) or validation['source_sha256'] != digest((package / 'resume.tex').read_bytes()):
            raise ValueError('Artifact changed; regenerate and inspect again')
        if payload.get('passed') is not True or not payload.get('reviewer') or not payload.get('notes'):
            raise ValueError('Require an actual visual reviewer and findings, not an automatic success flag')
        validation.update({'status': 'ready', 'visual_review': {**payload, 'at': now()}})
        store.write(f'packages/{job_id}/validation.json', validation)
    return validation
