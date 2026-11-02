"""ResumeForge guided editor preview.

Renders the EXISTING Executive/Harvard PDF templates. Sample CV data is
fictional and is never copied into the user's stored profile.
No remote services, API calls, or shared caches are used.
"""
from __future__ import annotations

import hashlib
import io
import json
from copy import deepcopy

import fitz
import streamlit as st
from PIL import Image, ImageDraw

from resumeforge.i18n import tr
from resumeforge.model import normalize_profile
from resumeforge.render import render_pdf

# Fully fictional demonstration candidate. Keep out of studio_cv.
DEMO_PROFILE = {
    "name": "Alex Morgan",
    "headline": "Operations & Project Specialist",
    "tagline": "Turning plans into better ways of working.",
    "location": "Example City, USA",
    "email": "alex.morgan@example.com",
    "phone": "+1 (202) 555-0142",
    "linkedin": "linkedin.com/in/example-candidate",
    "github": "",
    "summary": (
        "Operations and project specialist experienced in coordinating teams, "
        "improving workflows, and translating business needs into practical "
        "solutions. Skilled in project planning, reporting, stakeholder "
        "communication, and continuous improvement."
    ),
    "skills": [
        "Project coordination", "Process improvement", "Stakeholder communication",
        "Operational reporting", "Excel", "SQL", "Documentation", "Teamwork",
    ],
    "skill_groups": [
        {"title": "Operations", "items": ["Project coordination", "Process improvement", "Operational reporting"]},
        {"title": "Technology", "items": ["Excel", "SQL", "Documentation"]},
        {"title": "Collaboration", "items": ["Stakeholder communication", "Teamwork"]},
    ],
    "experience": [
        {
            "title": "Operations Coordinator",
            "organization": "Maplebrook Digital (fictional)",
            "period": "2022–Present",
            "bullets": [
                "Coordinated weekly project updates across business and technology teams.",
                "Prepared reporting dashboards to help managers track delivery milestones.",
                "Documented recurring processes and helped simplify internal workflows.",
            ],
        },
        {
            "title": "Project Assistant",
            "organization": "Harborline Services (fictional)",
            "period": "2019–2022",
            "bullets": [
                "Maintained project schedules and meeting documentation.",
                "Supported communication between service teams and clients.",
            ],
        },
    ],
    "education": [
        {"qualification": "Bachelor of Business Administration", "institution": "Example State University (fictional)", "year": "2019"},
    ],
    "projects": [
        {
            "name": "Workflow Reporting Dashboard",
            "technologies": "Excel · SQL",
            "description": "Created a fictional sample dashboard demonstrating weekly operational reporting.",
        },
        {
            "name": "Team Onboarding Guide",
            "technologies": "Process documentation",
            "description": "Prepared example onboarding materials to illustrate a project entry.",
        },
    ],
    "training": ["Example short course in project planning"],
    "languages": ["English — Fluent", "Spanish — Intermediate"],
    "extra_notes": "Available for hybrid or remote work (fictional example).",
    "raw_source_text": "",
    "source_file": "",
}

FOCUS_OPTIONS = {
    "About you": [
        ("name", "Full name"),
        ("headline", "Professional headline"),
        ("tagline", "Tagline"),
        ("contact", "Contact details"),
        ("summary", "Professional summary"),
        ("languages", "Languages"),
    ],
    "Work experience": [("experience", "Work experience")],
    "Education": [("education", "Education")],
    "Skills": [("skills", "Skills")],
    "Projects": [("projects", "Projects")],
    "Other details": [("training", "Courses and training"), ("notes", "Additional information")],
}

# Compact, local UI translations. Do not call Groq for fixed navigation text.
LOCALIZED = {
    "es": {
        "Guided CV preview": "Vista guiada del CV", "Example CV": "CV de ejemplo", "My CV": "Mi CV",
        "Preview design": "Diseño de vista previa", "Show me where": "Mostrar dónde aparece",
        "Where this goes": "Dónde aparece", "Example — fictional data": "Ejemplo — datos ficticios",
        "Your saved CV": "Tu CV guardado", "Page": "Página", "of": "de",
        "Highlighted on the actual CV": "Resaltado en el CV real", "No information saved yet": "Aún no hay información guardada",
        "Complete this section and save it to see your own CV here.": "Completa esta sección y guárdala para ver aquí tu CV.",
        "Preview unavailable": "Vista previa no disponible", "Your information has not changed.": "Tu información no ha cambiado.",
        "Fictional demonstration. It is never added to your CV.": "Demostración ficticia. Nunca se agrega a tu CV.",
        "Save your changes to refresh My CV.": "Guarda los cambios para actualizar Mi CV.",
        "This field is not displayed in the selected template.": "Este campo no aparece en la plantilla seleccionada.",
    },
    "de": {
        "Guided CV preview": "Geführte Lebenslaufvorschau", "Example CV": "Beispiel-Lebenslauf", "My CV": "Mein Lebenslauf",
        "Preview design": "Vorschau-Design", "Show me where": "Anzeigebereich",
        "Where this goes": "Hier erscheint es", "Example — fictional data": "Beispiel — fiktive Daten",
        "Your saved CV": "Ihr gespeicherter Lebenslauf", "Page": "Seite", "of": "von",
        "Highlighted on the actual CV": "Im echten Lebenslauf hervorgehoben", "No information saved yet": "Noch keine Angaben gespeichert",
        "Complete this section and save it to see your own CV here.": "Füllen Sie diesen Bereich aus und speichern Sie ihn, um Ihren Lebenslauf hier zu sehen.",
        "Preview unavailable": "Vorschau nicht verfügbar", "Your information has not changed.": "Ihre Angaben wurden nicht geändert.",
        "Fictional demonstration. It is never added to your CV.": "Fiktives Beispiel. Es wird Ihrem Lebenslauf nie hinzugefügt.",
        "Save your changes to refresh My CV.": "Speichern Sie Ihre Änderungen, um Mein Lebenslauf zu aktualisieren.",
        "This field is not displayed in the selected template.": "Dieses Feld wird in der gewählten Vorlage nicht angezeigt.",
    },
    "fr": {
        "Guided CV preview": "Aperçu guidé du CV", "Example CV": "CV d’exemple", "My CV": "Mon CV",
        "Preview design": "Modèle d’aperçu", "Show me where": "Afficher l’emplacement",
        "Where this goes": "Où cela apparaît", "Example — fictional data": "Exemple — données fictives",
        "Your saved CV": "Votre CV enregistré", "Page": "Page", "of": "sur",
        "Highlighted on the actual CV": "Surligné sur le véritable CV", "No information saved yet": "Aucune information enregistrée",
        "Complete this section and save it to see your own CV here.": "Remplissez cette rubrique et enregistrez-la pour voir votre CV ici.",
        "Preview unavailable": "Aperçu indisponible", "Your information has not changed.": "Vos informations n’ont pas été modifiées.",
        "Fictional demonstration. It is never added to your CV.": "Exemple fictif. Il n’est jamais ajouté à votre CV.",
        "Save your changes to refresh My CV.": "Enregistrez vos modifications pour actualiser Mon CV.",
        "This field is not displayed in the selected template.": "Ce champ n’apparaît pas dans le modèle choisi.",
    },
    "zh": {
        "Guided CV preview": "简历填写指引", "Example CV": "示例简历", "My CV": "我的简历",
        "Preview design": "预览模板", "Show me where": "查看对应位置",
        "Where this goes": "信息显示位置", "Example — fictional data": "示例 — 虚构资料",
        "Your saved CV": "已保存的简历", "Page": "第", "of": "共",
        "Highlighted on the actual CV": "已在实际简历中高亮显示", "No information saved yet": "尚未保存信息",
        "Complete this section and save it to see your own CV here.": "填写并保存本部分后，即可在此查看自己的简历。",
        "Preview unavailable": "无法预览", "Your information has not changed.": "您的信息未被修改。",
        "Fictional demonstration. It is never added to your CV.": "所有示例资料均为虚构，不会添加到您的简历中。",
        "Save your changes to refresh My CV.": "保存更改后更新“我的简历”。",
        "This field is not displayed in the selected template.": "所选模板不显示此字段。",
    },
    "ja": {
        "Guided CV preview": "履歴書の入力ガイド", "Example CV": "サンプル履歴書", "My CV": "自分の履歴書",
        "Preview design": "プレビューデザイン", "Show me where": "表示位置を確認",
        "Where this goes": "記載される場所", "Example — fictional data": "例 — 架空のデータ",
        "Your saved CV": "保存済みの履歴書", "Page": "ページ", "of": "全",
        "Highlighted on the actual CV": "実際の履歴書でハイライト表示", "No information saved yet": "保存された情報がありません",
        "Complete this section and save it to see your own CV here.": "この項目を入力して保存すると、ここに履歴書が表示されます。",
        "Preview unavailable": "プレビューを表示できません", "Your information has not changed.": "情報は変更されていません。",
        "Fictional demonstration. It is never added to your CV.": "架空のサンプルで、あなたの履歴書には追加されません。",
        "Save your changes to refresh My CV.": "変更を保存すると「自分の履歴書」が更新されます。",
        "This field is not displayed in the selected template.": "選択したテンプレートにはこの項目が表示されません。",
    },
    "nl": {
        "Guided CV preview": "Begeleide cv-voorvertoning", "Example CV": "Voorbeeld-cv", "My CV": "Mijn cv",
        "Preview design": "Voorbeeldontwerp", "Show me where": "Toon waar dit staat",
        "Where this goes": "Waar dit verschijnt", "Example — fictional data": "Voorbeeld — fictieve gegevens",
        "Your saved CV": "Je opgeslagen cv", "Page": "Pagina", "of": "van",
        "Highlighted on the actual CV": "Gemarkeerd in het echte cv", "No information saved yet": "Nog geen gegevens opgeslagen",
        "Complete this section and save it to see your own CV here.": "Vul dit onderdeel in en sla het op om je eigen cv hier te bekijken.",
        "Preview unavailable": "Voorvertoning niet beschikbaar", "Your information has not changed.": "Je gegevens zijn niet gewijzigd.",
        "Fictional demonstration. It is never added to your CV.": "Fictief voorbeeld. Het wordt nooit toegevoegd aan je cv.",
        "Save your changes to refresh My CV.": "Sla je wijzigingen op om Mijn cv te vernieuwen.",
        "This field is not displayed in the selected template.": "Dit veld wordt niet weergegeven in het gekozen sjabloon.",
    },
}

# The section mapping is explanatory—not a claim that every CV has the same coordinates.
PLACEMENT = {
    "Executive": {
        "name": "Your name is displayed prominently in the dark sidebar.",
        "headline": "Your professional headline appears below your name in the sidebar.",
        "tagline": "Your tagline appears in the Executive sidebar.",
        "contact": "Your location, email, phone, and links appear in the sidebar.",
        "summary": "Your professional summary appears under Professional Profile in the main column.",
        "languages": "Your spoken languages appear in the sidebar or a languages section.",
        "skills": "Your skills appear in Key Competencies and, when space allows, in the sidebar.",
        "experience": "Each job appears under Professional Experience with dates and achievements.",
        "education": "Education is listed under Qualifications or Education.",
        "projects": "Projects are listed under Projects, including tools and descriptions.",
        "training": "Courses and training appear below education and projects.",
        "notes": "Additional information appears near the end of your CV.",
    },
    "Harvard": {
        "name": "Your name appears in the header at the top of the CV.",
        "headline": "The current Harvard PDF template may not display the separate headline. Switch to Executive to preview it.",
        "tagline": "The current Harvard template does not show the optional tagline. Switch to Executive to preview it.",
        "contact": "Your contact details appear near the top, below your name.",
        "summary": "Your summary appears under Professional Summary.",
        "languages": "Languages appear in the languages section.",
        "skills": "Skills are shown as compact, readable skill tags.",
        "experience": "Experience appears as chronological roles under Professional Experience.",
        "education": "Qualifications appear in the Education section.",
        "projects": "Projects appear in the Projects section.",
        "training": "Courses are placed in the Training section.",
        "notes": "Additional information appears near the end of the CV.",
    },
}

# Explanations for new fields are translated locally; no live AI or tokens.
# Each note covers both layout options, so the displayed placement remains honest.
PLACEMENT_LOCALIZED = {
    "es": {
        "name": "Executive: barra lateral oscura. Harvard: encabezado superior.",
        "headline": "Executive: debajo del nombre. Harvard: puede no aparecer en el PDF.",
        "tagline": "Executive: barra lateral. Harvard: este campo no se muestra.",
        "contact": "Executive: barra lateral. Harvard: debajo del nombre, en la parte superior.",
        "summary": "Executive: Perfil profesional, a la derecha. Harvard: Perfil profesional.",
        "languages": "Executive: barra lateral o sección Idiomas. Harvard: sección Idiomas.",
        "skills": "Executive: Competencias principales y, según el espacio, barra lateral. Harvard: lista de habilidades.",
        "experience": "Sección Experiencia profesional, con cargos, fechas y logros.",
        "education": "Sección Formación académica y cualificaciones.",
        "projects": "Sección Proyectos, con herramientas y descripciones.",
        "training": "Sección Cursos o Formación complementaria.",
        "notes": "Sección Información adicional, cerca del final.",
    },
    "de": {
        "name": "Executive: dunkle Seitenleiste. Harvard: Kopfbereich oben.",
        "headline": "Executive: unter dem Namen. Harvard: möglicherweise nicht im PDF enthalten.",
        "tagline": "Executive: Seitenleiste. Harvard: dieses Feld wird nicht angezeigt.",
        "contact": "Executive: Seitenleiste. Harvard: im oberen Kopfbereich.",
        "summary": "Executive: Profil im Hauptbereich. Harvard: berufliches Profil.",
        "languages": "Executive: Seitenleiste oder Sprachbereich. Harvard: Sprachenbereich.",
        "skills": "Executive: Schlüsselkompetenzen und ggf. Seitenleiste. Harvard: Kompetenzübersicht.",
        "experience": "Berufserfahrung mit Positionen, Zeiträumen und Leistungen.",
        "education": "Bereich Ausbildung und Qualifikationen.",
        "projects": "Projektbereich mit Werkzeugen und Beschreibungen.",
        "training": "Bereich Fortbildungen und Kurse.",
        "notes": "Zusätzliche Angaben am Ende des Lebenslaufs.",
    },
    "fr": {
        "name": "Executive : colonne sombre. Harvard : en-tête en haut.",
        "headline": "Executive : sous le nom. Harvard : peut ne pas figurer dans le PDF.",
        "tagline": "Executive : colonne latérale. Harvard : ce champ est omis.",
        "contact": "Executive : colonne latérale. Harvard : en haut, sous le nom.",
        "summary": "Executive : profil dans la colonne principale. Harvard : profil professionnel.",
        "languages": "Executive : colonne latérale ou rubrique Langues. Harvard : rubrique Langues.",
        "skills": "Executive : compétences clés et parfois colonne latérale. Harvard : liste des compétences.",
        "experience": "Rubrique Expérience professionnelle : postes, dates et réalisations.",
        "education": "Rubrique Formation et qualifications.",
        "projects": "Rubrique Projets, avec outils et descriptions.",
        "training": "Rubrique Formations complémentaires.",
        "notes": "Informations complémentaires vers la fin du CV.",
    },
    "zh": {
        "name": "Executive：深色侧栏；Harvard：页面顶部标题。",
        "headline": "Executive：姓名下方；Harvard：可能不显示于 PDF。",
        "tagline": "Executive：侧栏；Harvard：不显示此字段。",
        "contact": "Executive：侧栏；Harvard：顶部姓名下方。",
        "summary": "Executive：正文中的职业简介；Harvard：职业简介部分。",
        "languages": "Executive：侧栏或语言部分；Harvard：语言部分。",
        "skills": "Executive：核心能力及部分侧栏；Harvard：技能清单。",
        "experience": "工作经历部分，包括职位、日期和成果。",
        "education": "教育背景及资格部分。",
        "projects": "项目部分，包括工具和说明。",
        "training": "课程及培训部分。",
        "notes": "简历末尾的补充信息部分。",
    },
    "ja": {
        "name": "Executive：濃色のサイドバー。Harvard：最上部の見出し。",
        "headline": "Executive：氏名の下。Harvard：PDFに表示されない場合があります。",
        "tagline": "Executive：サイドバー。Harvard：この項目は表示されません。",
        "contact": "Executive：サイドバー。Harvard：上部の氏名の下。",
        "summary": "Executive：本文の職務概要。Harvard：職務概要セクション。",
        "languages": "Executive：サイドバーまたは言語欄。Harvard：言語欄。",
        "skills": "Executive：主要スキルと一部のサイドバー。Harvard：スキル一覧。",
        "experience": "職務経歴欄に役職、在籍期間、実績を記載します。",
        "education": "学歴・資格欄に記載します。",
        "projects": "プロジェクト欄にツールと説明を記載します。",
        "training": "研修・講座欄に記載します。",
        "notes": "履歴書の末尾にある追加情報欄です。",
    },
    "nl": {
        "name": "Executive: donkere zijbalk. Harvard: kop bovenaan.",
        "headline": "Executive: onder de naam. Harvard: mogelijk niet zichtbaar in de PDF.",
        "tagline": "Executive: zijbalk. Harvard: dit veld wordt weggelaten.",
        "contact": "Executive: zijbalk. Harvard: bovenaan onder de naam.",
        "summary": "Executive: profiel in de hoofdtekst. Harvard: profielsectie.",
        "languages": "Executive: zijbalk of talenrubriek. Harvard: talenrubriek.",
        "skills": "Executive: kerncompetenties en soms zijbalk. Harvard: vaardighedenoverzicht.",
        "experience": "Werkervaring met functies, periodes en prestaties.",
        "education": "Onderdeel Opleiding en kwalificaties.",
        "projects": "Projecten met gebruikte tools en beschrijvingen.",
        "training": "Onderdeel Cursussen en trainingen.",
        "notes": "Aanvullende informatie aan het einde van je cv.",
    },
}

# Search uses actual rendered PDF text, not guessed coordinates or a second mock layout.
FALLBACK_TERMS = {
    "name": ["ALEX MORGAN"],
    "headline": ["Operations & Project Specialist"],
    "tagline": ["Turning plans into better ways of working"],
    "contact": ["example.com"],
    "summary": ["PROFESSIONAL PROFILE", "PROFESSIONAL SUMMARY"],
    "languages": ["LANGUAGES", "Languages"],
    "skills": ["KEY COMPETENCIES", "CORE SKILLS", "SKILLS"],
    "experience": ["PROFESSIONAL EXPERIENCE", "EXPERIENCE"],
    "education": ["EDUCATION", "QUALIFICATIONS"],
    "projects": ["PROJECTS"],
    "training": ["TRAINING", "COURSES"],
    "notes": ["ADDITIONAL INFORMATION", "OTHER INFORMATION"],
}


LIVE_TEXT = {
    "es": {
        "Start entering your details to see them here.": "Empieza a introducir tus datos para verlos aquí.",
        "Live preview only — press Save to keep your changes.": "Vista previa en directo: pulsa Guardar para conservar los cambios.",
    },
    "de": {
        "Start entering your details to see them here.": "Gib deine Angaben ein, um sie hier zu sehen.",
        "Live preview only — press Save to keep your changes.": "Live-Vorschau: Klicke auf Speichern, um die Änderungen zu übernehmen.",
    },
    "fr": {
        "Start entering your details to see them here.": "Commencez à saisir vos informations pour les voir ici.",
        "Live preview only — press Save to keep your changes.": "Aperçu en direct : cliquez sur Enregistrer pour conserver vos modifications.",
    },
    "zh": {
        "Start entering your details to see them here.": "开始输入信息即可在此查看。",
        "Live preview only — press Save to keep your changes.": "实时预览：点击“保存”才会保留修改。",
    },
    "ja": {
        "Start entering your details to see them here.": "情報を入力すると、ここに表示されます。",
        "Live preview only — press Save to keep your changes.": "ライブプレビューです。変更を保存するには［保存］を押してください。",
    },
    "nl": {
        "Start entering your details to see them here.": "Begin met het invullen van je gegevens om ze hier te zien.",
        "Live preview only — press Save to keep your changes.": "Livevoorbeeld: klik op Opslaan om je wijzigingen te bewaren.",
    },
}

def _t(value: str) -> str:
    lang = st.session_state.get("rf_interface_lang", "en")
    return LIVE_TEXT.get(lang, {}).get(value, LOCALIZED.get(lang, {}).get(value, tr(value)))


def _needles(profile: dict, focus: str) -> list[str]:
    """Strong signals for the specific value; broad section headings are fallbacks."""
    result = []
    def add(value):
        if isinstance(value, str) and value.strip():
            value = value.strip()
            result.append(value if len(value) < 80 else value[:65].rsplit(" ", 1)[0])

    if focus in {"name", "headline", "tagline", "summary"}:
        add(profile.get(focus))
    elif focus == "contact":
        for key in ("email", "location", "phone"):
            add(profile.get(key))
    elif focus == "languages":
        for item in profile.get("languages", [])[:2]:
            add(item)
    elif focus == "skills":
        for item in profile.get("skills", [])[:3]:
            add(item)
    elif focus == "experience":
        for job in profile.get("experience", [])[:2]:
            add(job.get("title"))
    elif focus == "education":
        for item in profile.get("education", [])[:2]:
            add(item.get("qualification"))
    elif focus == "projects":
        for item in profile.get("projects", [])[:2]:
            add(item.get("name"))
    elif focus == "training":
        for item in profile.get("training", [])[:2]:
            add(item)
    elif focus == "notes":
        add(profile.get("extra_notes"))
    return result


def _matches(page: fitz.Page, needles: list[str], limit: int = 8):
    matches = []
    for term in needles[:8]:
        try:
            rects = page.search_for(term, quads=False)
        except Exception:
            rects = []
        for rect in rects[:3]:
            if rect.is_empty or rect.is_infinite:
                continue
            matches.append(rect)
            if len(matches) >= limit:
                return matches
    return matches


def _focus_rectangles(document: fitz.Document, profile: dict, focus: str):
    """Return best page index and matching PDF coordinates for each PDF page."""
    strong = _needles(profile, focus)
    fallback = FALLBACK_TERMS.get(focus, [])
    matches_per_page = []
    best_idx, best_score = 0, -1
    for i, page in enumerate(document):
        primary = _matches(page, strong)
        secondary = _matches(page, fallback, 4)
        # A match to the candidate's actual text outranks a generic section label.
        score = len(primary) * 10 + len(secondary) * 2
        rects = primary if primary else secondary
        matches_per_page.append(rects)
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx, matches_per_page


def _pdf_for_session(profile: dict, style: str, photo: bytes | None):
    # Browser sessions do not share CV data or cached PDF content.
    raw = json.dumps(profile, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    key = hashlib.sha256(raw + b"|" + style.encode() + (photo or b"")).hexdigest()
    cached = st.session_state.get("rf_guide_cached_pdf")
    if cached and cached["key"] == key:
        return cached["pdf"]
    result = render_pdf(profile, style.lower(), photo=photo)
    st.session_state["rf_guide_cached_pdf"] = {"key": key, "pdf": result}
    return result


def _marked_page(page: fitz.Page, rects: list[fitz.Rect]):
    zoom = 1.45
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    drawer = ImageDraw.Draw(overlay, "RGBA")
    x_factor = pixmap.width / page.rect.width
    y_factor = pixmap.height / page.rect.height
    for rect in rects[:8]:
        x0 = max(1, int((rect.x0 - page.rect.x0) * x_factor) - 6)
        y0 = max(1, int((rect.y0 - page.rect.y0) * y_factor) - 4)
        x1 = min(image.width - 1, int((rect.x1 - page.rect.x0) * x_factor) + 6)
        y1 = min(image.height - 1, int((rect.y1 - page.rect.y0) * y_factor) + 4)
        if x1 > x0 and y1 > y0:
            drawer.rounded_rectangle((x0, y0, x1, y1), radius=6,
                                     fill=(50, 183, 202, 42), outline=(18, 151, 180, 245), width=3)
    image = Image.alpha_composite(image, overlay).convert("RGB")
    return image


def _has_content(cv: dict):
    return any(cv.get(key) for key in ("name", "headline", "summary", "experience", "education", "skills", "projects"))


# The editing preview intentionally uses preview-only placeholders so an
# unfinished CV does not look like an empty sheet of paper. These placeholders
# NEVER reach studio_cv, JSON backups, PDF downloads, or Word exports.
GUIDE_PROMPT = {
    "en": "Text in [brackets] is guidance for unfinished sections, not part of your saved CV or downloads.",
    "es": "El texto entre [corchetes] sirve de guía y no forma parte del CV guardado ni de las descargas.",
    "de": "Text in [Klammern] dient nur als Hilfe und erscheint nicht im gespeicherten oder heruntergeladenen Lebenslauf.",
    "fr": "Le texte entre [crochets] est une aide : il ne figure ni dans le CV enregistré ni dans les fichiers téléchargés.",
    "zh": "[方括号]中的文字只是填写提示，不会保存到简历或出现在下载文件中。",
    "ja": "[角括弧] 内の文言は入力ガイドです。保存する履歴書やダウンロードには含まれません。",
    "nl": "Tekst tussen [haken] is uitsluitend hulptekst en komt niet in het opgeslagen of gedownloade cv.",
}


def _simple_live_profile(cv: dict):
    """Make a full sample-layout preview WITHOUT modifying the real CV."""
    p = normalize_profile(deepcopy(cv))

    # The editor passes the assembled current draft; do not override it with
    # a second read from st.session_state. A stale or previous-revision widget
    # value could replace an entered email, phone, location, or link with blank.
    # Like all Streamlit inputs, changes enter Python after a field is committed
    # (typically Enter or leaving the field). The draft is never saved here.

    # Preview-only, unmistakable guidance; never silently fill the user's CV.
    placeholders = {
        "name": "[Your name]",
        "headline": "[Professional headline]",
        "tagline": "[Your optional tagline]",
        "email": "[Email address]",
        "phone": "[Phone number]",
        "location": "[City, Country]",
        "summary": "[Write a short professional summary describing your experience, strengths and goals.]",
    }
    has_missing = False
    for field, value in placeholders.items():
        if not str(p.get(field, "")).strip():
            p[field] = value
            has_missing = True

    if not p.get("skills") and not p.get("skill_groups"):
        p["skills"] = ["[Core skill]", "[Technical skill]", "[Professional strength]"]
        has_missing = True
    if not p.get("experience"):
        p["experience"] = [
            {"title": "[Job title]", "organization": "[Employer]",
             "period": "[Employment dates]",
             "bullets": ["[Describe an actual responsibility or verified achievement.]"]}
        ]
        has_missing = True
    if not p.get("education"):
        p["education"] = [
            {"qualification": "[Qualification or degree]",
             "institution": "[Institution]", "year": "[Year]"}
        ]
        has_missing = True
    if not p.get("projects"):
        p["projects"] = [
            {"name": "[Project name]", "technologies": "[Tools or technologies]",
             "description": "[Describe what you built, contributed or accomplished.]"}
        ]
        has_missing = True
    return p, has_missing


def render_guided_preview(cv: dict, category: str, current_style: str, photo: bytes | None = None):
    """Show the complete user CV draft in the real PDF templates, without extra controls."""
    with st.container(key="rf-guided-preview", border=True):
        st.markdown(f"#### :material/preview: {_t('Guided CV preview')}")
        style = st.selectbox(
            _t("Preview design"), ["Executive", "Harvard"],
            index=0 if current_style.lower() == "executive" else 1,
            key="rf_guide_style",
        )
        profile, has_placeholders = _simple_live_profile(cv)
        if has_placeholders:
            lang = st.session_state.get("rf_interface_lang", "en")
            st.caption(GUIDE_PROMPT.get(lang, GUIDE_PROMPT["en"]))
        st.caption(_t("Live preview only — press Save to keep your changes."))
        try:
            source_photo = photo if style == "Executive" else None
            pdf_bytes = _pdf_for_session(profile, style, source_photo)
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                if not len(doc):
                    st.warning(_t("Preview unavailable"))
                    return
                # Show every page, rather than hiding content behind a page selector.
                with st.container(height=740, border=False):
                    for page in doc:
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.28, 1.28), alpha=False)
                        st.image(pix.tobytes("png"), use_container_width=True)
        except Exception:
            # Keep private CV information and local paths out of error messages.
            st.warning(_t("Preview unavailable") + ". " + _t("Your information has not changed."))
