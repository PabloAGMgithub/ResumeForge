"""ResumeForge 2.0: local-first CV editor, two faithful templates, and optional AI rewrite.

Start with: python -m streamlit run app.py
"""
import io
import json
import os
from copy import deepcopy
from pathlib import Path

import fitz
import pandas as pd
from PIL import Image
import streamlit as st
import streamlit.components.v1 as components

from resumeforge.ai import suggest_rewrite
from resumeforge.importer import extract_profile
from resumeforge.model import normalize_profile
from resumeforge.render import render_pdf

BASE = Path(__file__).resolve().parent
USER_DATA = BASE / "local_data"

st.set_page_config(
    page_title="ResumeForge | Free CV Builder",
    page_icon=Image.open(BASE / "assets" / "resumeforge_icon.png"),
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown("""<style>
.block-container {padding-top:2rem;padding-bottom:3rem;max-width:1460px;}
[data-testid='stSidebar'] {background:#f3f5f8;}
h1,h2,h3 {color:#162339;} .subtle {color:#53647a;font-size:.92rem;}
.template-note {background:#f4f6f8;border-left:3px solid #a61c35;padding:13px 16px;border-radius:7px;}
</style>""",unsafe_allow_html=True)


def load_initial_profile():
    local = USER_DATA / "my_cv.json"
    demo = BASE / "examples" / "demo_cv.json"
    source = local if local.exists() else demo
    return normalize_profile(json.loads(source.read_text(encoding="utf-8")))

if "master" not in st.session_state:
    st.session_state.master = load_initial_profile()
    st.session_state.working = deepcopy(st.session_state.master)
    st.session_state.photo = (USER_DATA / "profile_photo.jpg").read_bytes() if (USER_DATA / "profile_photo.jpg").exists() else None
    st.session_state.art = None
    st.session_state.import_warnings = []
    st.session_state.editor_revision = 0
    st.session_state.target_role = ""
    st.session_state.job_desc = ""
    st.session_state.ai_suggestion = ""
    st.session_state.ai_locator = None


def lines_to_list(value):
    return [v.strip() for v in str(value).splitlines() if v.strip()]


def bullets_from_cell(value):
    return lines_to_list(value)


def value_to_text(v):
    return "" if pd.isna(v) else str(v).strip()


def dataframe(data,fields):
    return pd.DataFrame([{k:("\n".join(obj.get(k,[])) if isinstance(obj.get(k), list) else str(obj.get(k, ""))) for k in fields} for obj in data],columns=fields)


def from_dataframe(frame,fields,split_bullets=False):
    records=[]
    for row in frame.to_dict("records"):
        obj={k:value_to_text(row.get(k,"")) for k in fields}
        if not any(obj.values()): continue
        if split_bullets: obj["bullets"]=bullets_from_cell(obj["bullets"])
        records.append(obj)
    return records


def cached_pdf(profile_json, style, photo, art):
    return render_pdf(json.loads(profile_json),style,photo=photo,brain=art)


def pdf_for_working():
    try:
        return cached_pdf(json.dumps(st.session_state.working,ensure_ascii=False,sort_keys=True),
                          st.session_state.style,st.session_state.photo,st.session_state.art)
    except Exception as err:
        st.error(f"PDF generation failed: {err}")
        return None

with st.sidebar:
    st.title("ResumeForge Studio")
    st.caption("Local-first • editable CVs • no subscription")
    st.divider()
    st.write("**Current profile**")
    st.write(st.session_state.working.get("name") or "Unnamed profile")
    st.caption(f"{len(st.session_state.working.get('experience',[]))} roles · {len(st.session_state.working.get('education',[]))} qualifications")
    if st.button("Reset working copy from master",use_container_width=True):
        st.session_state.working=deepcopy(st.session_state.master)
        st.session_state.editor_revision+=1
        st.rerun()
    if st.button("Make working copy my master",use_container_width=True):
        st.session_state.master=deepcopy(st.session_state.working)
        st.success("Updated in this session. Download the Master JSON below to keep it between sessions.")
    st.download_button("Download master profile (JSON)",json.dumps(st.session_state.master,ensure_ascii=False,indent=2),
                       "resumeforge_master_cv.json","application/json",use_container_width=True)
    st.caption("Files are processed in memory. This app makes no AI API calls unless you explicitly request one.")

st.title("ResumeForge 2.0")
st.write("Import a CV, refine every detail, choose your exact Executive or Harvard-style template, and export a selectable-text PDF.")
tabs=st.tabs(["1 · Import CV","2 · My Information","3 · Target & AI","4 · Templates","5 · Preview & Export"])

with tabs[0]:
    st.subheader("Import an existing CV or saved master profile")
    st.write("Supported files: **PDF**, **DOCX**, and ResumeForge **JSON**. The original extracted text is retained for review.")
    upload=st.file_uploader("Choose your existing CV",type=["pdf","docx","json"],key="cv_import")
    if st.button("Extract information from uploaded file",type="primary",disabled=upload is None):
        try:
            source=upload.getvalue()
            if upload.name.lower().endswith(".json"):
                profile=normalize_profile(json.loads(source.decode("utf8")))
                warnings=[]
            else:
                profile,warnings=extract_profile(source,upload.name)
            st.session_state.master=deepcopy(profile)
            st.session_state.working=deepcopy(profile)
            st.session_state.import_warnings=warnings
            st.session_state.editor_revision+=1
            st.success("Imported. Please review all extracted fields in My Information.")
        except Exception as exc:
            st.error(f"Could not read this file: {exc}")
    for warning in st.session_state.import_warnings:
        st.warning(warning)
    st.markdown("<div class='template-note'><b>Information preservation:</b> PDFs can contain columns, images, or text stored in unusual order. Anything the parser cannot place confidently stays in <b>Additional information</b> and the original text. Confirm that dates, qualifications, and achievements are categorized correctly before exporting a professional CV.</div>",unsafe_allow_html=True)
    with st.expander("View original extracted text (read-only)"):
        st.text_area("Source transcript",st.session_state.working.get('raw_source_text','') or 'No source transcript in this profile.',height=250,disabled=True)

with tabs[1]:
    st.subheader("Edit your complete professional information")
    st.write("Edits change only the **working copy**. Your master stays unchanged until you explicitly promote the working version.")
    p=st.session_state.working
    key=f"_r{st.session_state.editor_revision}"
    with st.form("complete_profile_editor"+key):
        a,b=st.columns(2)
        with a:
            name=st.text_input("Full name",p.get('name',''))
            headline=st.text_input("Professional headline",p.get('headline',''))
            location=st.text_input("Location",p.get('location',''))
            email=st.text_input("Email",p.get('email',''))
            linkedin=st.text_input("LinkedIn",p.get('linkedin',''))
        with b:
            tagline=st.text_input("Tagline",p.get('tagline',''))
            phone=st.text_input("Phone",p.get('phone',''))
            github=st.text_input("GitHub",p.get('github',''))
            languages=st.text_area("Languages — one per line","\n".join(p.get('languages',[])),height=102)
        summary=st.text_area("Professional summary",p.get('summary',''),height=115)
        skills=st.text_area("Individual skills — one per line","\n".join(p.get('skills',[])),height=140)
        groups='\n'.join(g.get('title','')+': '+ '; '.join(g.get('items',[])) for g in p.get('skill_groups',[]))
        skill_groups=st.text_area("Executive competencies — one group per line: Heading: skill; skill; skill",groups,height=115)
        st.markdown("#### Professional experience")
        st.caption("Add or remove rows using the table controls. For bullets, enter one accomplishment per line.")
        jobs=st.data_editor(dataframe(p.get('experience',[]),['title','organization','period','bullets']),num_rows='dynamic',hide_index=True,
                            column_config={'title':'Role','organization':'Employer','period':'Dates','bullets':st.column_config.TextColumn('Bullets (newline-separated)',width='large')},use_container_width=True)
        st.markdown("#### Education and certifications")
        eds=st.data_editor(dataframe(p.get('education',[]),['qualification','institution','year']),num_rows='dynamic',hide_index=True,use_container_width=True)
        st.markdown("#### Projects")
        projects=st.data_editor(dataframe(p.get('projects',[]),['name','technologies','description']),num_rows='dynamic',hide_index=True,use_container_width=True)
        training=st.text_area("Additional courses / training — one per line","\n".join(p.get('training',[])),height=105)
        extra=st.text_area("Additional information not yet assigned to a section",p.get('extra_notes',''),height=140)
        applied=st.form_submit_button("Apply changes to working CV",type='primary',use_container_width=True)
    if applied:
        new=deepcopy(p)
        new.update(name=name,headline=headline,location=location,email=email,linkedin=linkedin,tagline=tagline,
                   phone=phone,github=github,summary=summary,skills=lines_to_list(skills),languages=lines_to_list(languages),
                   training=lines_to_list(training),extra_notes=extra)
        new['experience']=from_dataframe(jobs,['title','organization','period','bullets'],split_bullets=True)
        new['education']=from_dataframe(eds,['qualification','institution','year'])
        new['projects']=from_dataframe(projects,['name','technologies','description'])
        g=[]
        for ln in lines_to_list(skill_groups):
            title,sep,items=ln.partition(':')
            if title.strip(): g.append({'title':title.strip(),'items':[it.strip() for it in items.split(';') if it.strip()] if sep else []})
        new['skill_groups']=g
        st.session_state.working=normalize_profile(new)
        st.success("Changes applied to your working CV.")

with tabs[2]:
    st.subheader("Tailor your CV to a job")
    st.write("Your master profile is never rewritten automatically. AI suggestions require your approval and a provider key you supply.")
    st.session_state.target_role=st.text_input("Target role",value=st.session_state.target_role,placeholder="e.g., AI Quality Analyst")
    st.session_state.job_desc=st.text_area("Job description (optional)",value=st.session_state.job_desc,height=130)
    if st.session_state.job_desc:
        terms=set(x.lower().strip('.,;:') for x in st.session_state.job_desc.split() if len(x)>4)
        ranks=[]
        for i,job in enumerate(st.session_state.working.get('experience',[])):
            content=(job.get('title','')+' '+job.get('organization','')+' '+' '.join(job.get('bullets',[]))).lower()
            match={term for term in terms if term in content}
            ranks.append((len(match),job.get('title',''),', '.join(sorted(match)[:8])))
        if ranks:
            st.caption("Relevance hints (keyword overlap only; original chronology is preserved)")
            st.dataframe(pd.DataFrame(sorted(ranks,reverse=True),columns=['Overlaps','Role','Example matches']),hide_index=True)
    st.markdown("#### Optional AI-assisted rewriting")
    choices={'Professional summary':('summary',None,None)}
    for ji,job in enumerate(st.session_state.working.get('experience',[])):
        for bi,bullet in enumerate(job.get('bullets',[])):
            choices[f"{job.get('title','Role')} · bullet {bi+1} · {bullet[:35]}"] =('bullet',ji,bi)
    selected=st.selectbox("Choose a statement to improve",list(choices.keys()))
    kind,ji,bi=choices[selected]
    original=(st.session_state.working.get('summary','') if kind=='summary' else st.session_state.working['experience'][ji]['bullets'][bi])
    st.text_area("Original, verified wording",original,disabled=True,height=95)
    with st.expander("Connect a model (optional, never automatic)"):
        endpoint=st.text_input("Trusted API endpoint (full /chat/completions URL)",placeholder="https://your-provider.example/v1/chat/completions")
        model=st.text_input("Model ID",placeholder="Provider's available model ID")
        api_key=st.text_input("API key (session only)",type="password")
        allowed=st.checkbox("I authorize sending this statement and job details to the API provider I selected.")
        if st.button("Generate an AI rewrite",disabled=not allowed):
            try:
                with st.spinner("Requesting proposed wording..."):
                    result=suggest_rewrite(original,st.session_state.target_role,st.session_state.job_desc,endpoint,model,api_key)
                    st.session_state.ai_suggestion=result
                    st.session_state.ai_locator=(kind,ji,bi)
            except Exception as exc:
                st.error(str(exc))
    if st.session_state.ai_suggestion:
        proposed=st.text_area("AI suggestion — edit before approving",st.session_state.ai_suggestion,height=110)
        st.warning("Check every figure, employer, responsibility, and qualification. AI wording may be inaccurate.")
        if st.button("Approve and apply this wording to the working copy"):
            if st.session_state.ai_locator==choices[selected]:
                if kind=='summary':st.session_state.working['summary']=proposed.strip()
                else:st.session_state.working['experience'][ji]['bullets'][bi]=proposed.strip()
                st.session_state.ai_suggestion=''
                st.session_state.editor_revision+=1
                st.success("Applied. The master profile remains unchanged.")
            else:st.warning("The selected field changed. Generate a fresh suggestion for it.")

with tabs[3]:
    st.subheader("Choose your reference design")
    st.session_state.style=st.radio("CV template",['Executive','Harvard'],horizontal=True,
                                     help="Executive matches your AI-brain three-page example; Harvard matches your clean burgundy two-page example.").lower()
    if st.session_state.style=='executive':
        st.write("**Executive reference:** A4, charcoal sidebar, portrait, subtle AI brain, four pale skill panels, navy headings.")
        picture=st.file_uploader("Replace profile photo (only for Executive)",type=['jpg','jpeg','png','webp'],key='photo_up')
        if picture:
            photo_data=picture.getvalue()
            try:
                Image.open(io.BytesIO(photo_data)).verify()
                st.session_state.photo=photo_data
            except Exception as exc:st.error(f"Invalid image: {exc}")
        if st.session_state.photo:
            st.image(st.session_state.photo,width=130,caption="Executive portrait")
        art=st.file_uploader("Optional: replace the AI brain illustration",type=['png','jpg','jpeg','webp'],key='brain_up')
        if art:
            st.session_state.art=art.getvalue()
        if st.button("Use original AI brain art"):
            st.session_state.art=None
    else:
        st.write("**Harvard-style reference:** Letter, centered name and contact details, burgundy section rules and job markers, rounded text-based skill pills, and gray project cards. No portrait.")
    st.caption("The reference templates have fixed colors and typography in their CSS. You can later add optional presets without changing the originals.")

with tabs[4]:
    st.subheader("Verify every page and export")
    st.write("The preview below comes from the actual PDF exporter, not an approximate browser layout.")
    pdf=pdf_for_working()
    if pdf:
        doc=fitz.open(stream=pdf,filetype='pdf')
        n=len(doc)
        a,b,c=st.columns([1,1,1])
        a.metric('PDF pages',n)
        b.metric('Experience entries',len(st.session_state.working.get('experience',[])))
        c.metric('Skills',len(st.session_state.working.get('skills',[])))
        preview_page=st.selectbox('Preview page',list(range(1,n+1)),format_func=lambda i:f'Page {i} / {n}')
        page=doc[preview_page-1]
        pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
        st.image(pix.tobytes('png'),use_container_width=True)
        text_length=sum(len(pg.get_text()) for pg in doc)
        if text_length < 60: st.error('Exported PDF has little or no selectable text; check the renderer.')
        else:st.success(f'PDF contains {text_length:,} characters of selectable text.')
        if st.session_state.working.get('extra_notes'):
            st.warning('Some imported information is still uncategorized. Verify it before applying to jobs.')
        stem=''.join(c if c.isalnum() else '_' for c in st.session_state.working.get('name','CV')).strip('_') or 'CV'
        st.download_button('Download finished PDF',data=pdf,file_name=f'{stem}_{st.session_state.style}.pdf',mime='application/pdf',type='primary',use_container_width=True)
        st.download_button('Download editable working profile (JSON)',data=json.dumps(st.session_state.working,indent=2,ensure_ascii=False),
                           file_name=f'{stem}_working_profile.json',mime='application/json',use_container_width=True)
