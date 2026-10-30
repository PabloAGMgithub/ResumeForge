"""ResumeForge Studio preview: a guided multipage interface for the existing CV engine.

"""
from __future__ import annotations
from resumeforge.i18n import tr, tr_html

from resumeforge.ai_chat import ai_assistant_page
from resumeforge.cv_review import render_cv_review

import io
import json
import html
from copy import deepcopy
from pathlib import Path

import fitz
import streamlit as st
from PIL import Image

from resumeforge.ai import suggest_rewrite
from resumeforge.importer import extract_profile
from resumeforge.model import empty_profile, normalize_profile, flatten_skills
from resumeforge.render import render_pdf
from resumeforge.docx_export import build_docx
from resumeforge.cv_languages import render_language_choice, render_localized_pdf, LANGUAGES, ui

BASE = Path(__file__).resolve().parent
ICON = BASE / "assets" / "resumeforge_icon.png"

st.set_page_config(
    page_title="ResumeForge Studio | Build your CV",
    page_icon=Image.open(ICON) if ICON.exists() else "📄",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("<style>" + (BASE / "ui" / "studio.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)


def initialize():
    """All profile state is scoped to this browser session, not the web server."""
    if "studio_master" not in st.session_state:
        st.session_state.studio_master = empty_profile()
        st.session_state.studio_cv = empty_profile()
        st.session_state.studio_photo = None
        st.session_state.studio_art = None
        st.session_state.studio_style = "Executive"
        st.session_state.studio_import_warnings = []
        st.session_state.studio_revision = 0
        st.session_state.studio_target = ""
        st.session_state.studio_description = ""
        st.session_state.studio_proposal = ""
        st.session_state.studio_proposal_key = None
        st.session_state.studio_group_slots = 0
        st.session_state.studio_photo_nonce = 0
        st.session_state.studio_art_nonce = 0


def save_cv(updated):
    st.session_state.studio_cv = normalize_profile(updated)
    st.session_state.studio_revision += 1


def lines(value):
    return [s.strip() for s in str(value).splitlines() if s.strip()]


def text(value):
    return html.escape(str(value or ""))


def page_header(stage, title, description):
    st.markdown(f"<div class='rf-eyebrow'>{text(stage)}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='rf-heading'>{text(title)}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='rf-sub'>{text(description)}</div>", unsafe_allow_html=True)


def route(key):
    st.switch_page(PAGES[key])


def load_demo():
    sample = BASE / "examples" / "demo_cv.json"
    data = normalize_profile(json.loads(sample.read_text(encoding="utf-8")))
    st.session_state.studio_master = deepcopy(data)
    save_cv(data)
    st.session_state.studio_photo = None
    st.session_state.studio_art = None
    st.session_state.studio_import_warnings = []


def import_file(upload):
    source = upload.getvalue()
    if upload.name.lower().endswith(".json"):
        profile = normalize_profile(json.loads(source.decode("utf-8")))
        warnings = []
    else:
        profile, warnings = extract_profile(source, upload.name)
    st.session_state.studio_master = deepcopy(profile)
    save_cv(profile)
    st.session_state.studio_photo = None
    st.session_state.studio_art = None
    st.session_state.studio_import_warnings = warnings
    st.session_state.studio_proposal = ""
    st.session_state.studio_proposal_key = None


def career_overview():
    cv = st.session_state.studio_cv
    name = cv.get("name", "") or "Untitled CV"
    st.markdown(tr("### ✦ ResumeForge"))
    st.caption(tr("BUILD SOMETHING GREAT"))
    st.divider()
    st.caption(tr("YOUR CURRENT CV"))
    st.markdown(f"**{text(name)}**")
    st.caption(tr(f"{len(cv.get('experience', []))} jobs · {len(cv.get('education', []))} qualifications · {len(flatten_skills(cv))} skills"))
    st.divider()
    with st.expander(tr("Save & restore")):
        if st.button(tr("Save a checkpoint"), use_container_width=True):
            st.session_state.studio_master = deepcopy(cv)
            st.success(tr("Saved for this session. Download a backup to retain it."))
        if st.button(tr("Restore checkpoint"), use_container_width=True):
            save_cv(deepcopy(st.session_state.studio_master))
            st.rerun()
        st.download_button(tr("Download editable backup"), json.dumps(cv, ensure_ascii=False, indent=2),
                           "ResumeForge_CV_backup.json", "application/json", use_container_width=True)
    st.caption(tr("Your CV is not saved permanently on this website. Download a backup to keep it."))


def home():
    st.markdown(tr_html("""
    <section class="rf-hero"><div class="rf-kicker">✦ RESUMEFORGE · YOUR NEXT OPPORTUNITY STARTS HERE</div>
      <h1>Your experience deserves a great CV.</h1>
      <p>Bring your story to life. Upload a résumé or start fresh, edit your details,
         choose your design, and download a polished CV.</p>
      <div class="rf-chips"><span class="rf-chip">✓ Free and Easy to use</span>
        <span class="rf-chip">✓ No account required</span>
        <span class="rf-chip">✓ Two professional templates</span></div>
    </section>
    <div class="rf-eyebrow">HOW IT WORKS</div>
    <div class="rf-step-grid">
      <div class="rf-step"><b>01 · BEGIN</b><h3>Start with your CV</h3><p>Upload a file, or create a new CV.</p></div>
      <div class="rf-step"><b>02 · PERSONALIZE</b><h3>Tell your story</h3><p>Edit work, studies, skills and more.</p></div>
      <div class="rf-step"><b>03 · CHOOSE</b><h3>Pick your design</h3><p>Executive or Harvard-style.</p></div>
      <div class="rf-step"><b>04 · DOWNLOAD</b><h3>Make it yours</h3><p>Preview and export a real PDF.</p></div>
    </div>
    """), unsafe_allow_html=True)
    page_header(tr("LET'S BEGIN"), tr("How would you like to start?"), tr("Choose a starting point. You can always change your information later."))
    c1,c2,c3=st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown(tr("#### :material/upload_file: Upload an existing CV"))
            st.write(tr("Already have a résumé? Let ResumeForge read it for you."))
            if st.button(tr("Upload my CV"), use_container_width=True, type="primary"):
                route("upload")
    with c2:
        with st.container(border=True):
            st.markdown(tr("#### :material/edit_note: Create from scratch"))
            st.write(tr("Start with an empty profile and add your own information."))
            if st.button(tr("Create a new CV"), use_container_width=True):
                st.session_state.studio_master = empty_profile()
                save_cv(empty_profile())
                st.session_state.studio_photo = None
                route("editor")
    with c3:
        with st.container(border=True):
            st.markdown(tr("#### :material/visibility: Explore with an example"))
            st.write(tr("See how ResumeForge works using fictional information."))
            if st.button(tr("Try the example"), use_container_width=True):
                load_demo()
                route("editor")
    st.info(tr("PDF imports aren't always perfect. Please verify names, dates, achievements, and qualifications before downloading."))


def upload_page():
    page_header(tr("STEP 1 · UPLOAD"), tr("Bring your CV into ResumeForge"), tr("Choose a PDF, Word document, or saved ResumeForge backup. We'll help organize the information."))
    upload = st.file_uploader(tr("Select your CV file"), type=["pdf", "docx", "json"], key="studio_upload")
    if st.button(tr("Read my CV"), type="primary", disabled=upload is None):
        try:
            import_file(upload)
        except Exception as err:
            st.error(tr(f"Couldn't import this file: {err}"))
        else:
            st.success(tr("CV imported! Review the information before choosing your design."))
            route("editor")
    for warning in st.session_state.studio_import_warnings:
        st.warning(warning)
    with st.expander(tr("What if some information is missing?")):
        st.write(tr("PDFs sometimes store text in columns or unusual positions. Unrecognized text is retained for review, not silently discarded. You can add any missing work or qualifications in the editor."))
    with st.expander(tr("See imported source text")):
        st.text_area(tr("Original text"), st.session_state.studio_cv.get("raw_source_text", ""), height=230, disabled=True)
    if st.button(tr("I'd rather type everything myself")):
        st.session_state.studio_master = empty_profile()
        save_cv(empty_profile())
        route("editor")


def save_contact(values):
    p=deepcopy(st.session_state.studio_cv)
    p.update(values)
    save_cv(p)


def contact_tab():
    p=st.session_state.studio_cv
    rev=st.session_state.studio_revision
    with st.form(f"identity_{rev}"):
        st.markdown(tr("#### Who are you?"))
        a,b=st.columns(2)
        with a:
            name=st.text_input(tr("Full name"),p.get("name", ""))
            headline=st.text_input(tr("Professional headline (optional)"),p.get("headline", ""),help=tr("For example: Bilingual Educator | Healthcare Professional"))
            email=st.text_input(tr("Email"),p.get("email", ""))
            location=st.text_input(tr("City and country"),p.get("location", ""))
        with b:
            phone=st.text_input(tr("Phone number"),p.get("phone", ""))
            tagline=st.text_input(tr("Tagline (optional)"),p.get("tagline", ""),help=tr("A short statement about the value you bring; mainly used in Executive style."))
            linkedin=st.text_input(tr("LinkedIn (optional)"),p.get("linkedin", ""))
            github=st.text_input(tr("Portfolio or GitHub (optional)"),p.get("github", ""))
        st.markdown(tr("#### Tell your story"))
        summary=st.text_area(tr("Professional summary"),p.get("summary", ""),height=145)
        languages=st.text_area(tr("Languages (one per line)"),"\n".join(p.get("languages", [])),height=100)
        submitted=st.form_submit_button(tr("Save profile details"),type="primary",use_container_width=True)
    if submitted:
        save_contact({"name":name,"headline":headline,"email":email,"location":location,"phone":phone,"tagline":tagline,"linkedin":linkedin,"github":github,"summary":summary,"languages":lines(languages)})
        st.success(tr("Your profile details have been saved."))


def skills_tab():
    p=st.session_state.studio_cv
    st.markdown(tr("#### Your skills"))
    if flatten_skills(p):
        st.markdown("".join(f'<span class="rf-tag">{text(s)}</span>' for s in flatten_skills(p)),unsafe_allow_html=True)
    else:
        st.info(tr("No skills added yet. Add your strengths below."))
    with st.form(f"skill_form_{st.session_state.studio_revision}"):
        skills=st.text_area(tr("Skills (one per line)"),"\n".join(p.get("skills", [])),height=165,
                            help=tr("These become rounded skill tags in the Harvard-style CV."))
        st.caption(tr("To remove a skill, delete its line and save."))
        pressed=st.form_submit_button(tr("Save skills"),type="primary")
    if pressed:
        copy=deepcopy(p);copy["skills"]=lines(skills);save_cv(copy);st.success(tr("Skills saved."))
    st.markdown(tr("#### Organize skills for the Executive design (optional)"))
    st.caption(tr("Executive-style groups are optional. If you skip them, ResumeForge can group your individual skills automatically."))
    with st.form(f"groups_{st.session_state.studio_revision}"):
        groups=deepcopy(p.get("skill_groups", []))
        groups += [{"title":"","items":[]}] * (1 + st.session_state.studio_group_slots)
        changed=[]
        for i,g in enumerate(groups):
            a,b=st.columns([1,2])
            with a: label=st.text_input(tr(f"Category {i+1}"),g.get("title", ""),key=f"group_title_{i}_{st.session_state.studio_revision}")
            with b: content=st.text_input(tr(f"Skills for category {i+1} (separate with ;)"),"; ".join(g.get("items", [])),key=f"group_items_{i}_{st.session_state.studio_revision}")
            if label.strip():changed.append({"title":label.strip(),"items":[v.strip() for v in content.split(";") if v.strip()]})
        save=st.form_submit_button(tr("Save skill categories"))
    if save:
        copy=deepcopy(p);copy["skill_groups"]=changed;save_cv(copy);st.success(tr("Categories saved."))
    if st.button(tr("Add another category")):
        st.session_state.studio_group_slots += 1
        st.rerun()


def edit_records(section,title,fields,default,bullets=False):
    p=st.session_state.studio_cv
    records=p.get(section, [])
    st.markdown(f"#### {title}")
    st.caption(tr("Open a card to edit. Save each card before moving to another step."))
    for i,record in enumerate(records):
        label=record.get(fields[0][0], "") or f"New {title.lower()} entry"
        secondary=record.get(fields[1][0], "") or "Add details"
        with st.expander(f"{i+1}. {label} · {secondary}",expanded=(not record.get(fields[0][0]) or not record.get(fields[1][0]))):
            with st.form(f"rec_{section}_{i}_{st.session_state.studio_revision}"):
                result={}
                for field,label_,help_ in fields:
                    v=record.get(field,[] if field=="bullets" else "")
                    if field=="bullets":
                        result[field]=lines(st.text_area(label_,"\n".join(v),height=150,help=help_))
                    elif field=="description":
                        result[field]=st.text_area(label_,str(v),height=100,help=help_)
                    else:
                        result[field]=st.text_input(label_,str(v),help=help_)
                saved=st.form_submit_button(tr("Save this entry"),type="primary")
            if saved:
                copy=deepcopy(p);copy[section][i]=result;save_cv(copy)
                st.success(tr("Entry saved."))
            c1,c2,c3=st.columns(3)
            with c1:
                if st.button(tr("↑ Move up"),key=f"up_{section}_{i}",disabled=i==0):
                    copy=deepcopy(p);copy[section][i-1],copy[section][i]=copy[section][i],copy[section][i-1]
                    save_cv(copy);st.rerun()
            with c2:
                if st.button(tr("↓ Move down"),key=f"down_{section}_{i}",disabled=i==len(records)-1):
                    copy=deepcopy(p);copy[section][i],copy[section][i+1]=copy[section][i+1],copy[section][i]
                    save_cv(copy);st.rerun()
            with c3:
                if st.button(tr("Remove"),key=f"rm_{section}_{i}"):
                    copy=deepcopy(p);copy[section].pop(i);save_cv(copy);st.rerun()
    if not records: st.info(tr(f"Nothing in {title.lower()} yet. Use Add below to begin."))
    if st.button(tr(f"+ Add {title.lower()} entry"),key=f"add_{section}",type="secondary"):
        copy=deepcopy(p);copy[section].append(deepcopy(default));save_cv(copy);st.rerun()


EXPERIENCE=[("title","Job title",None),("organization","Employer / organization",None),("period","Dates (e.g., 2022–Present)",None),("bullets","Achievements (one per line)","Start with an action verb, and include verified results where possible.")]
EDUCATION=[("qualification","Qualification / certification",None),("institution","School or institution",None),("year","Year or date",None)]
PROJECTS=[("name","Project name",None),("technologies","Tools / technologies (optional)",None),("description","What did you build or accomplish?",None)]


def extras_tab():
    p=st.session_state.studio_cv
    with st.form(f"extras_{st.session_state.studio_revision}"):
        training=st.text_area(tr("Additional courses or training (one per line)"),"\n".join(p.get("training", [])),height=130)
        extra=st.text_area(tr("Other information from your imported CV"),p.get("extra_notes", ""),height=125)
        saved=st.form_submit_button(tr("Save additional information"),type="primary")
    if saved:
        copy=deepcopy(p);copy["training"]=lines(training);copy["extra_notes"]=extra;save_cv(copy)
        st.success(tr("Additional information saved."))
    if p.get("extra_notes"):
        st.warning(tr("Review other information before applying to jobs. Move important items into the appropriate sections when possible."))
    with st.expander(tr("View original imported text")):
        st.text_area(tr("Source text"),p.get("raw_source_text", ""),disabled=True,height=230)


def editor_page():
    page_header(tr("STEP 2 · PERSONALIZE"), tr("Make your story shine"), tr("Update your information using simple cards. Your original imported text remains available for reference."))
    cv=st.session_state.studio_cv
    st.caption(tr(f"Editing: {cv.get('name') or 'Untitled CV'}"))
    options=["About you","Work experience","Education","Skills","Projects","Other details"]
    category=st.radio(tr("What would you like to edit?"),options, format_func=tr, horizontal=True, key="studio_editor_category")
    st.divider()
    if category=="About you":contact_tab()
    elif category=="Work experience":edit_records("experience","Work experience",EXPERIENCE,{"title":"","organization":"","period":"","bullets":[]},True)
    elif category=="Education":edit_records("education","Education",EDUCATION,{"qualification":"","institution":"","year":""})
    elif category=="Skills":skills_tab()
    elif category=="Projects":edit_records("projects","Projects",PROJECTS,{"name":"","technologies":"","description":""})
    else:extras_tab()
    st.divider()
    c1,c2=st.columns(2)
    with c1:
        if st.button(tr("← Back to upload"),use_container_width=True):route("upload")
    with c2:
        if st.button(tr("Continue to design →"),use_container_width=True,type="primary"):route("design")


def improve_page():
    page_header(tr("OPTIONAL · IMPROVE"), tr("Tailor your CV for the opportunity"), tr("Focus on the roles that matter. AI suggestions require your permission and your chosen provider's key."))
    st.session_state.studio_target=st.text_input(tr("Target job title"),value=st.session_state.studio_target)
    st.session_state.studio_description=st.text_area(tr("Job description (optional)"),value=st.session_state.studio_description,height=150)
    if st.session_state.studio_description.strip():
        terms={v.lower().strip(".,;:()") for v in st.session_state.studio_description.split() if len(v)>4}
        results=[]
        for job in st.session_state.studio_cv.get("experience", []):
            content=(job.get("title", "")+" "+job.get("organization", "")+" "+" ".join(job.get("bullets", []))).lower()
            overlaps=sorted(t for t in terms if t in content)
            results.append({"Role":job.get("title", ""),"Keyword matches":len(overlaps),"Examples":", ".join(overlaps[:8])})
        if results:st.dataframe(sorted(results,key=lambda r:r["Keyword matches"],reverse=True),hide_index=True,use_container_width=True)
        st.caption(tr("Keyword overlap is a rough guide, not an applicant tracking system score."))
    st.markdown(tr("#### Optional AI rewriting"))
    cv=st.session_state.studio_cv
    choices={"Professional summary":("summary",None,None)}
    for j,job in enumerate(cv.get("experience", [])):
        for i,b in enumerate(job.get("bullets", [])):
            choices[f"{job.get('title','Job')} · accomplishment {i+1}: {b[:35]}"]=("bullet",j,i)
    choice=st.selectbox(tr("Select a statement to improve"),list(choices))
    kind,j,i=choices[choice]
    original=cv.get("summary", "") if kind=="summary" else cv["experience"][j]["bullets"][i]
    st.text_area(tr("Verified original wording"),original,disabled=True,height=110)
    with st.expander(tr("Connect your own AI provider (optional)")):
        st.warning(tr("Only connect to a provider you trust. Your chosen statement and job description will be sent to that provider if you consent."))
        endpoint=st.text_input(tr("HTTPS API endpoint ending in /chat/completions"),placeholder=tr("https://provider.example/v1/chat/completions"))
        model=st.text_input(tr("Provider's model ID"))
        key=st.text_input(tr("Your API key (not saved)"),type="password")
        consent=st.checkbox(tr("I agree to send this statement and job description to my chosen AI provider."))
        if st.button(tr("Suggest improved wording"),disabled=not consent or not original.strip()):
            try:
                with st.spinner(tr("Generating suggestion...")):
                    proposed=suggest_rewrite(original,st.session_state.studio_target,st.session_state.studio_description,endpoint,model,key)
                st.session_state.studio_proposal=proposed
                st.session_state.studio_proposal_key=(kind,j,i)
            except Exception as exc:st.error(tr(f"Suggestion unavailable: {exc}"))
    if st.session_state.studio_proposal:
        proposal=st.text_area(tr("Review and edit the suggestion"),st.session_state.studio_proposal,height=130)
        st.info(tr("Verify every claim before approving. The assistant must not add experience, metrics, or qualifications you don't have."))
        if st.button(tr("Approve wording and update this CV"),type="primary"):
            if st.session_state.studio_proposal_key!=(kind,j,i):
                st.error(tr("You changed the selected statement. Generate a new suggestion."))
            else:
                copy=deepcopy(cv)
                if kind=="summary":copy["summary"]=proposal.strip()
                else:copy["experience"][j]["bullets"][i]=proposal.strip()
                save_cv(copy)
                st.session_state.studio_proposal=""
                st.success(tr("Applied to your current CV only."))
    if st.button(tr("Continue to design →"),type="primary"):route("design")


def design_page():
    page_header(tr("STEP 3 · DESIGN"), tr("Choose your signature look"), tr("Both templates preserve the original ResumeForge PDF styling. You can change your selection before downloading."))
    a,b=st.columns(2)
    with a:
        st.markdown(tr_html("""<div class="rf-template"><div class="rf-mini-exec"><div class="side"><i></i><em></em><em></em><em></em></div><div class="body"><strong></strong><em></em><em></em><em></em><em></em><strong style="width:61%;margin-top:16px"></strong><em></em><em></em></div></div><h3>Executive</h3><p>Bold navy accents, a charcoal sidebar, optional portrait, and AI-inspired artwork. A4 format.</p></div>"""),unsafe_allow_html=True)
        if st.button(tr("Choose Executive"),use_container_width=True,type="primary" if st.session_state.studio_style=="Executive" else "secondary"):
            st.session_state.studio_style="Executive";st.rerun()
    with b:
        st.markdown(tr_html("""<div class="rf-template"><div class="rf-mini-harvard"><strong></strong><em></em><em></em><div class="rule"></div><em></em><em></em><span class="pill"></span><span class="pill"></span><span class="pill"></span><div class="rule"></div><em></em><em></em><em></em></div><h3>Harvard-style</h3><p>Clean white layout, burgundy job markers, rounded skill tags, and polished project cards. US Letter.</p></div>"""),unsafe_allow_html=True)
        if st.button(tr("Choose Harvard-style"),use_container_width=True,type="primary" if st.session_state.studio_style=="Harvard" else "secondary"):
            st.session_state.studio_style="Harvard";st.rerun()
    st.success(tr(f"Selected design: **{st.session_state.studio_style}**"))
    if st.session_state.studio_style=="Executive":
        st.markdown(tr("#### Your portrait (optional)"))
        pic=st.file_uploader(tr("Upload a portrait for your Executive CV"),type=["jpg","jpeg","png","webp"],key=f"studio_photo_upload_{st.session_state.studio_photo_nonce}")
        if pic is not None:
            try:
                photo=pic.getvalue()
                Image.open(io.BytesIO(photo)).verify()
                st.session_state.studio_photo=photo
            except Exception as exc:st.error(tr(f"Couldn't read photo: {exc}"))
        if st.session_state.studio_photo:
            st.image(st.session_state.studio_photo,width=145)
            if st.button(tr("Remove portrait")):
                st.session_state.studio_photo=None
                st.session_state.studio_photo_nonce+=1
                st.rerun()
        with st.expander(tr("Customize AI artwork (advanced)")):
            art=st.file_uploader(tr("Replace the original decorative artwork (optional)"),type=["png","jpg","jpeg","webp"],key=f"studio_brain_upload_{st.session_state.studio_art_nonce}")
            if art is not None:st.session_state.studio_art=art.getvalue()
            if st.button(tr("Use original artwork")):
                st.session_state.studio_art=None
                st.session_state.studio_art_nonce+=1
                st.rerun()
    st.caption(tr("Harvard-style does not include a portrait. Photos are never inserted into that PDF."))
    a,b=st.columns(2)
    with a:
        if st.button(tr("← Back to edit"),use_container_width=True):route("editor")
    with b:
        if st.button(tr("Preview my CV →"),type="primary",use_container_width=True):route("export")


def export_page():
    page_header(tr("STEP 4 · DOWNLOAD"), tr("Your CV is almost ready"), tr("View each exported page and download the finished PDF. The preview is produced by the real PDF renderer."))
    cv=st.session_state.studio_cv
    st.caption(tr(f"{st.session_state.studio_style} design · {cv.get('name') or 'Untitled CV'}"))
    if not (cv.get("name") or cv.get("experience") or cv.get("education") or cv.get("summary")):
        st.info(tr("Your CV is empty. Add your information or try the example to begin."))
        if st.button(tr("Add my details"),type="primary"):route("editor")
        return
    original_cv = cv
    render_cv_review(original_cv, on_approve=save_cv)
    cv, export_language, export_ready = render_language_choice(original_cv)
    if not export_ready:
        return
    try:
        with st.spinner(tr("Preparing your CV preview...")):
            result = (render_pdf(cv,st.session_state.studio_style.lower(),photo=st.session_state.studio_photo,brain=st.session_state.studio_art) if export_language == "en"
                      else render_localized_pdf(cv,st.session_state.studio_style.lower(),photo=st.session_state.studio_photo,brain=st.session_state.studio_art,language=export_language))
    except Exception as exc:
        st.error(tr(f"PDF couldn't be generated: {exc}"))
        st.caption(tr("Please review your profile or check the Playwright/Chromium installation."))
        return
    doc=fitz.open(stream=result,filetype="pdf")
    try:
        count=len(doc)

        with st.container(key="rf-preview-stats"):
            a, b, c = st.columns(3)

            a.metric("Pages", count)
            b.metric("Work entries", len(cv.get("experience", [])))
            c.metric("Skills", len(flatten_skills(cv)))

            selected = st.selectbox(
                tr("Page to preview"),
                list(range(1, count + 1)),
                format_func=lambda i: f"Page {i} of {count}"
            )
        rendered=doc[selected-1].get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False)
        st.image(rendered.tobytes("png"),use_container_width=True)
        n_chars=sum(len(page.get_text()) for page in doc)
    finally:
        doc.close()
    if n_chars<60:st.error(tr("PDF may not contain enough selectable text. Verify the export before sending it."))
    else:st.success(tr(f"PDF ready — {n_chars:,} characters of selectable text."))
    if cv.get("extra_notes"):
        st.warning(tr("You still have unclassified information in this CV. Review it before applying."))
    name="".join(ch if ch.isalnum() else "_" for ch in cv.get("name", "CV")).strip("_") or "CV"
    st.download_button(tr("↓ Download my finished PDF"),data=result,
                       file_name=f"{name}_{st.session_state.studio_style.lower()}_{export_language}.pdf",mime="application/pdf",type="primary",use_container_width=True)
    st.download_button(
        tr("Download editable Word CV (.docx)"),
        data=build_docx(cv, st.session_state.studio_style, language=export_language, photo=st.session_state.studio_photo, brain=st.session_state.studio_art),
        file_name=f"{name}_{st.session_state.studio_style.lower()}_{export_language}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )
    st.download_button(tr("Download editable CV backup (JSON)"),data=json.dumps(original_cv,ensure_ascii=False,indent=2),
                       file_name=f"{name}_editable.json",mime="application/json",use_container_width=True)
    if st.button(tr("← Make another change")):
        route("editor")


initialize()
with st.sidebar:
    st.selectbox(tr("Interface language / Idioma"), list(LANGUAGES),
                 format_func=lambda code: LANGUAGES[code],
                 key="rf_interface_lang")

PAGES = {
    "home": st.Page(home, title=ui("Welcome"), icon=":material/home:", url_path="welcome", default=True),
    "upload": st.Page(upload_page, title=ui("Upload CV"), icon=":material/upload_file:", url_path="upload"),
    "editor": st.Page(editor_page, title=ui("Edit details"), icon=":material/edit_note:", url_path="editor"),
    "ai": st.Page(ai_assistant_page, title=ui("AI Assistant"), icon=":material/smart_toy:", url_path="ai-assistant"),
    "design": st.Page(design_page, title=ui("Choose design"), icon=":material/palette:", url_path="design"),
    "export": st.Page(export_page, title=ui("Preview & download"), icon=":material/picture_as_pdf:", url_path="download"),
}

page=st.navigation(list(PAGES.values()),position="sidebar")
with st.sidebar:
    st.divider()
    career_overview()
page.run()
