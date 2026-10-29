"""Conservative first-pass CV import with native parsing for both supplied reference layouts.

All source text is retained. An arbitrary PDF cannot be guaranteed to expose its logical
structure; misclassified or uncategorized material is clearly marked for human review.
"""
from __future__ import annotations
import io
import re
from pathlib import Path
from docx import Document
import fitz
from .model import empty_profile

HEADINGS = {
    'summary': ('professional profile','profile','professional summary','summary','about me','objective'),
    'skills': ('technical skills','technical skills & core competencies','key competencies','skills','core competencies'),
    'experience': ('professional experience','employment history','work experience','experience','employment'),
    'education': ('education & professional qualifications','education','academic background','qualifications'),
    'projects': ('projects','selected projects','personal projects'),
    'training': ('additional technical training','training','courses','certifications'),
    'languages': ('languages','language skills'),
}
EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}')
DATE = re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|\b20\d{2}\b|\bPresent\b',re.I)


def section_key(line: str):
    key = re.sub(r'[^a-z0-9 &]', '',line.casefold()).strip()
    if key.startswith('professional experience') and 'continued' in key:return 'experience'
    for group,names in HEADINGS.items():
        if key in names:return group
    return None


def _is_sidebar(page):
    if not (590 <= page.rect.width <= 600):return False
    for drawing in page.get_drawings():
        c=drawing.get('fill'); box=drawing['rect']
        if c and .23<c[0]<.28 and box.x0<30 and 140<box.width<150 and box.height>700:
            return True
    return False


def read_text(blob:bytes,filename:str):
    ext=Path(filename).suffix.lower()
    if ext=='.pdf':
        with fitz.open(stream=blob,filetype='pdf') as doc:
            if _is_sidebar(doc[0]):
                left=doc[0].get_text('text',clip=fitz.Rect(23,26,167,800),sort=False)
                right='\n\n'.join(page.get_text('text',clip=fitz.Rect(172,29,558,810),sort=False) for page in doc)
                return left+'\n\n'+right,[]
            texts=[p.get_text('text',sort=True) for p in doc]
            return '\n\n'.join(texts), (["At least one page has little or no selectable text; image-only content may require OCR and manual review."] if any(len(t.strip())<50 for t in texts) else [])
    if ext=='.docx':
        doc=Document(io.BytesIO(blob))
        lines=[p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                lines.append(' | '.join(c.text for c in row.cells))
        for section in doc.sections:
            for para in section.header.paragraphs:
                if para.text.strip():lines.insert(0,para.text)
        return '\n'.join(lines),[]
    raise ValueError('Choose a PDF or DOCX document.')


def _date_like(line:str):
    s=line.strip()
    return bool(len(s)<45 and DATE.search(s) and not s.startswith('•') and not re.search(r'[.!?;]',s)
                and not any(word in s.lower() for word in ('university','business','applied','managed','developed')))


def _parse_jobs(lines):
    result=[]; unknown=[]; i=0
    while i<len(lines):
        title=lines[i]
        if section_key(title)=='experience':i+=1;continue
        if i+1<len(lines) and ('|' in lines[i+1] and DATE.search(lines[i+1].split('|')[-1])):
            meta=lines[i+1];org,_,period=meta.rpartition('|');i+=2
        elif i+2<len(lines) and _date_like(lines[i+1]) and not lines[i+2].startswith('•'):
            period=lines[i+1];org=lines[i+2];i+=3
        else:
            unknown.append(lines[i]);i+=1;continue
        job={'title':title.strip(),'organization':org.strip(),'period':period.strip(),'bullets':[]}
        while i<len(lines):
            curr=lines[i]
            if section_key(curr)=='experience':i+=1;break
            if i+1<len(lines) and (('|' in lines[i+1] and DATE.search(lines[i+1].split('|')[-1])) or _date_like(lines[i+1])):
                break
            if curr.startswith(('•','●','- ')):
                job['bullets'].append(curr.lstrip('•●- ').strip())
            elif job['bullets']:
                # Newline within the previous wrapped bullet.
                spacer='' if job['bullets'][-1].endswith('-') else ' '
                job['bullets'][-1] += spacer+curr
            else:
                unknown.append(curr)
            i+=1
        result.append(job)
    return result,unknown


def _parse_education(lines):
    result=[];unknown=[];i=0
    while i<len(lines):
        title=lines[i].strip()
        if i+1>=len(lines):unknown.append(title);break
        line=lines[i+1].strip()
        # Reference styles use either ' | YYYY' or ' · YYYY'.
        if re.search(r'(?:\||·)\s*(?:19|20)\d{2}\s*$',line):
            match=re.match(r'^(.*?)\s*[|·]\s*((?:19|20)\d{2})\s*$',line)
            inst,yr=match.group(1),match.group(2)
            result.append({'qualification':title,'institution':inst,'year':yr});i+=2
        else:unknown.append(title);i+=1
    return result,unknown


def _parse_projects_linear(lines):
    """Parse 3-column logical blocks: name, technology, description(s)."""
    items=[]; unknown=[];i=0
    while i<len(lines):
        if i+2>=len(lines):unknown+=lines[i:];break
        name=lines[i]
        technologies=lines[i+1]
        if len(name)>65 or (not any(x in technologies for x in ('·','Python','HTML','CSS','JavaScript','Streamlit','Java'))):
            unknown.append(name);i+=1;continue
        i+=2; description=[]
        while i<len(lines):
            if i+2<len(lines) and len(lines[i])<65 and any(t in lines[i+1] for t in ('·','Python','JavaScript','HTML','CSS')):
                break
            description.append(lines[i]);i+=1
        items.append({'name':name,'technologies':technologies,'description':' '.join(description)})
    return items,unknown


def _get_harvard_projects(blob):
    """Recover each project from individually positioned spans in two-column cards."""
    entries=[]
    with fitz.open(stream=blob,filetype='pdf') as doc:
        for page in doc:
            title_boxes=[]
            for block in page.get_text('dict')['blocks']:
                if block['type']!=0:continue
                for line in block['lines']:
                    for span in line['spans']:
                        if span['text'].strip()=='PROJECTS' and 'Bold' in span['font']:
                            title_boxes.append(span['bbox'])
            if not title_boxes: continue
            y0=min(box[3] for box in title_boxes)+4
            next_section=page.search_for('ADDITIONAL TECHNICAL TRAINING')
            y1=min((r.y0-1 for r in next_section if r.y0>y0),default=page.rect.height-35)
            columns=[[],[]]
            for block in page.get_text('dict')['blocks']:
                if block['type']!=0:continue
                for line in block['lines']:
                    y=line['bbox'][1]
                    if not y0<=y<y1:continue
                    for span in line['spans']:
                        text=span['text'].strip()
                        if text:
                            col=0 if span['bbox'][0]<275 else 1
                            columns[col].append((y,text))
            for lines in columns:
                ordered=sorted(lines,key=lambda t:t[0])
                vals=[text for y,text in ordered]
                parsed,_=_parse_projects_linear(vals)
                for obj in parsed:
                    y=next((y for y,text in ordered if text==obj['name']),y0)
                    entries.append((y,obj))
    return [obj for _,obj in sorted(entries,key=lambda t:t[0])]


def extract_profile(blob:bytes,filename:str):
    raw,warnings=read_text(blob,filename)
    data=empty_profile()
    data.update(raw_source_text=raw,source_file=filename)
    lines=[s.strip() for s in raw.splitlines() if s.strip()]
    if not lines:return data,warnings+['No selectable text found. Scanned CVs require OCR.']
    first='\n'.join(lines[:22]);full='\n'.join(lines)
    if em:=EMAIL.search(full): data['email']=em.group(0)
    for j,line in enumerate(lines[:16]):
        if line.isupper() and 2<=len(line.split())<=5 and len(line)<55 and not section_key(line):
            name=line
            if j+1<len(lines) and lines[j+1].isupper() and len(lines[j+1].split())<=2 and not section_key(lines[j+1]) and len(lines[j+1])<26:
                name+=' '+lines[j+1]
            data['name']=name.title();break
    if not data['name']:data['name']=lines[0] if len(lines[0])<65 else ''
    for line in lines[:12]:
        if '•' in line and ',' in line and '@' in line:
            data['location']=line.split('•')[0].strip()
            break
    if ph:=re.search(r'\+\d{1,3}[\s-]?(?:\d[\s-]?){7,12}',first):data['phone']=ph.group(0).strip()
    if filename.lower().endswith('.pdf'):
        try:
            with fitz.open(stream=blob,filetype='pdf') as pdf:
                for link in pdf[0].get_links():
                    url=link.get('uri','')
                    if 'linkedin.com/in/' in url:data['linkedin']=url
                    if 'github.com/' in url:data['github']=url
        except Exception:pass
    for line in lines[:25]:
        if 'linkedin:' in line.lower() and not data['linkedin']:
            data['linkedin']=re.split(r'LinkedIn:\s*',line,flags=re.I)[-1].split('•')[0].strip()
        if 'github:' in line.lower() and not data['github']:
            data['github']=re.split(r'GitHub:\s*',line,flags=re.I)[-1].split('•')[0].strip()
        if 'github.com/' in line.lower() and not data['github']:
            data['github']=re.search(r'github\.com/[A-Za-z0-9_-]+',line,re.I).group(0)
    for line in lines[:22]:
        if re.search(r'\b(?:Bolivia|USA|United Kingdom|Canada|Germany)\b',line,re.I) and len(line)<65 and '@' not in line:
            data['location']=line;break
    if data.get('github','').lower().startswith('github ·'):
        data['github']='github.com/'+data['github'].split('·',1)[-1].strip()

    parts={k:[] for k in HEADINGS};residual=[];current=None;seen_sections=set()
    for line in lines:
        section=section_key(line)
        if section:
            current=section;seen_sections.add(section)
        elif current:
            parts[current].append(line)
        else:residual.append(line)
    if parts['summary']:
        data['summary']=' '.join(parts['summary'])

    if 'skills' in seen_sections and not parts['skills']:
        warnings.append('The skills heading is present, but the skills themselves are not selectable text (likely image-based). Add or verify them in the editor.')
    if parts['skills']:
        grouped=[];group=None
        for line in parts['skills']:
            if line.isupper() and not line.startswith('•') and len(line)<60:
                group={'title':line.title(),'items':[]};grouped.append(group)
            elif line.startswith('•'):
                item=line.lstrip('• ').strip()
                if group is None:
                    group={'title':'Core Skills','items':[]};grouped.append(group)
                group['items'].append(item)
        data['skill_groups']=grouped[:12]
        skills=[]
        for group in grouped:
            for s in group['items']:
                skills.extend([item.strip() for item in s.split('·') if item.strip()])
        if skills:data['skills']=list(dict.fromkeys(skills))
        else:
            warnings.append('The skills section contains no selectable text; its pills may be embedded images. Add skills manually, or import a saved ResumeForge master JSON.')

    if parts['experience']:
        data['experience'],job_issues=_parse_jobs(parts['experience'])
    else:job_issues=[]
    if parts['education']:
        data['education'],edu_issues=_parse_education(parts['education'])
    else:edu_issues=[]
    if parts['projects']:
        data['projects'],project_issues=_parse_projects_linear(parts['projects'])
        if filename.lower().endswith('.pdf'):
            try:
                with fitz.open(stream=blob,filetype='pdf') as test_doc:
                    is_letter=abs(test_doc[0].rect.width-612)<1
                if is_letter:
                    column_projects=_get_harvard_projects(blob)
                    if column_projects:
                        data['projects']=column_projects
                        project_issues=[]
            except Exception as exc:warnings.append(f'Could not classify multi-column projects: {exc}')
    else:project_issues=[]
    if parts['training']:
        text=' '.join(parts['training']).rstrip('.')
        data['training']=[x.strip() for x in text.split(';') if x.strip()]
    if parts['languages']:
        data['languages']=[x.strip() for x in re.split(r'\s*\|\s*|\s*•\s*', ' '.join(parts['languages'])) if x.strip()]
    if not data.get('languages'):
        try:
            start=lines.index('LANGUAGES')
            data['languages']=[x.strip() for x in lines[start+1:start+4] if ('—' in x or '-' in x)]
        except ValueError:pass

    # Do not duplicate known contact, organization and headline in the extra data section.
    remnants=[]
    if job_issues:remnants.append('EXPERIENCE (unclassified)\n'+'\n'.join(job_issues))
    if edu_issues:remnants.append('EDUCATION (unclassified)\n'+'\n'.join(edu_issues))
    if project_issues:remnants.append('PROJECTS (unclassified)\n'+'\n'.join(project_issues))
    leftover=[l for l in residual if not (l.isupper() and len(l.split())<=3) and l not in (data.get('email'),data.get('location')) and '@' not in l and 'github' not in l.lower() and 'linkedin' not in l.lower() and not l.strip().startswith('+')]
    if any('TECHNOLOGY' in l and 'OPERATIONS' in l for l in leftover):
        headline=next(l for l in leftover if 'TECHNOLOGY' in l and 'OPERATIONS' in l)
        data['headline']=headline.replace('  ',' ').strip()
        leftover=[l for l in leftover if l!=headline]
    if 'Bridging technology, people' in leftover:
        i=leftover.index('Bridging technology, people')
        if i+1<len(leftover):
            data['tagline']=leftover[i]+' '+leftover[i+1]
            leftover=leftover[:i]+leftover[i+2:]
    # Include potentially valuable tagline/contact wording that was not categorized.
    if leftover:remnants.insert(0,'OTHER\n'+'\n'.join(leftover))
    data['extra_notes']='\n\n'.join(remnants)
    warnings.append('Review all automatically classified entries and Additional information before using the CV for a real job application.')
    return data,warnings
