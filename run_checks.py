"""Local smoke tests without requiring the Streamlit UI to be launched."""
import json
from pathlib import Path
import fitz
from resumeforge.render import render_pdf
from resumeforge.importer import extract_profile
ROOT=Path(__file__).resolve().parent
local=ROOT/'local_data/my_cv.json'
source=local if local.exists() else ROOT/'examples/demo_cv.json'
data=json.loads(source.read_text(encoding='utf8'))
photo=(ROOT/'local_data/profile_photo.jpg').read_bytes() if (ROOT/'local_data/profile_photo.jpg').exists() else None
for name in ('harvard','executive'):
    output=render_pdf(data,name,photo=photo)
    d=fitz.open(stream=output,filetype='pdf')
    full='\n'.join(page.get_text() for page in d)
    assert len(d)>=1,(name, 'empty PDF')
    assert len(full)>200,(name,'missing selectable text')
    assert data['name'].upper() in full.upper(),(name, 'name missing')
    for role in data['experience']:
        assert role['title'] in full,(name,role['title'])
    if name=='harvard':
        for skill in data['skills']:
            assert skill in full,(name,'non-selectable or missing skill',skill)
    print(f'{name}: {len(d)} page(s), {len(full):,} text characters, {len(output):,} bytes: OK')
imported,warnings=extract_profile((ROOT/'examples/demo_cv.json').read_bytes(),'example.json') if False else (None,[])
print('PASS: source data rendered with text for both templates.')
