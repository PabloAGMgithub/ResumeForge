"""Render the two document references as selectable-text HTML/PDF."""
from __future__ import annotations
import base64
import math
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .model import normalize_profile, flatten_skills

ROOT = Path(__file__).resolve().parent.parent
ENV = Environment(loader=FileSystemLoader(str(ROOT / 'templates')), autoescape=select_autoescape(['html']))


def data_uri(blob: bytes | None, mimetype='image/png'):
    return 'data:' + mimetype + ';base64,' + base64.b64encode(blob).decode('ascii') if blob else ''


def _estimate_job(job):
    # Conservative approximation for 375pt column, 9pt Carlito. A real PDF is
    # rendered afterwards and can be visually checked before downloading.
    bullet_lines = sum(max(1, math.ceil(len(str(t)) / 87)) for t in job.get('bullets', []))
    return 33 + 11.8 * bullet_lines + 5 * len(job.get('bullets', [])) + 9


def _pack_executive(profile):
    pages = [{'index': 0, 'blocks': [], 'used': 0}]
    def new_page():
        pages.append({'index': len(pages), 'blocks': [], 'used': 0})
    def add(kind, height, **kw):
        if pages[-1]['blocks'] and pages[-1]['used'] + height > 825:
            new_page()
        pages[-1]['blocks'].append({'type': kind, **kw})
        pages[-1]['used'] += height
    if profile.get('summary'):
        add('profile', 50 + 13 * math.ceil(len(profile['summary']) / 94))
    if profile.get('skill_groups'):
        max_top=max([len(x.get('items', [])) for x in profile['skill_groups'][:2]] or [0])
        max_bottom=max([len(x.get('items', [])) for x in profile['skill_groups'][2:4]] or [0])
        add('skills', 64 + 14 * (max_top + max_bottom) + 24)
    elif flatten_skills(profile):
        items=flatten_skills(profile)
        profile['skill_groups']=[{'title':'Core Skills', 'items':items[:8]}, {'title':'Technical Skills', 'items':items[8:16]},
                                 {'title':'More Skills', 'items':items[16:24]}, {'title':'Other', 'items':items[24:]}]
        add('skills', 240)
    jobs=profile.get('experience', [])
    first_page_jobs = 0
    if jobs:
        add('heading', 29, text='Professional Experience')
        for i, job in enumerate(jobs):
            height=_estimate_job(job) * .82
            # The reference intentionally places two roles on its first sheet.
            if pages[-1]['index'] == 0 and first_page_jobs >= 2:
                new_page()
                add('heading', 28, text='Professional Experience — Continued')
            elif pages[-1]['used'] + height > 815:
                new_page()
                add('heading', 28, text='Professional Experience — Continued')
            add('role', height, job=job)
            if pages[-1]['index']==0: first_page_jobs += 1

    # In original reference qualifications begin on a separate sheet; retain
    # this design choice if preceding experience exists.
    if jobs and any((profile.get(k) for k in ('education','projects','training','languages'))):
        new_page()
    if profile.get('education'):
        add('education', 35+len(profile['education'])*39)
    if profile.get('projects'):
        add('projects', 42+math.ceil(len(profile['projects'])/2)*95)
    if profile.get('training'):
        add('training', 45+12*math.ceil(len('; '.join(profile['training']))/94))
    if profile.get('languages'):
        add('languages', 37)
    if profile.get('extra_notes'):
        add('notes', 50 + 12 * math.ceil(len(profile['extra_notes'])/92))
    return pages


def render_html(profile: dict, template: str, *, photo: bytes | None = None, brain: bytes | None = None):
    p=normalize_profile(profile)
    t=template.lower().strip()
    if t not in ('harvard', 'executive'):
        raise ValueError('Choose Harvard or Executive.')
    ctx={'p':p, 'skills':flatten_skills(p), 'css':(ROOT/'templates'/f'{t}.css').read_text(encoding='utf8')}
    if t=='executive':
        ctx.update(pages=_pack_executive(p), photo=data_uri(photo, 'image/jpeg' if photo and photo[:3]==b'\xff\xd8\xff' else 'image/png'),
                   brain=data_uri(brain if brain is not None else (ROOT/'assets'/'ai_brain_art.png').read_bytes()))
    return ENV.get_template(f'{t}.html').render(**ctx)



def render_pdf(profile: dict, template: str, *,
               photo: bytes | None = None,
               brain: bytes | None = None):

    from playwright.sync_api import sync_playwright

    markup = render_html(
        profile,
        template,
        photo=photo,
        brain=brain
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        try:
            page = browser.new_page()

            page.set_content(markup, wait_until="load")

            page.evaluate("() => document.fonts.ready")

            pdf_bytes = page.pdf(
                print_background=True,
                prefer_css_page_size=True,
                margin={
                    "top": "0",
                    "bottom": "0",
                    "left": "0",
                    "right": "0"
                }
            )

            return pdf_bytes

        finally:
            browser.close()
