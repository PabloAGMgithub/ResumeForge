"""Static, local interface translations. CV content is never translated here.

Generate missing language-pack entries at development time with build_ui_packs.py.
Language packs are ordinary JSON files and do NOT need live AI requests.
"""
from functools import lru_cache
from pathlib import Path
import json
import re
import streamlit as st

LANG_CODES={'en','es','de','fr','zh','ja','nl'}
PACK_DIR=Path(__file__).resolve().parent/'i18n_packs'

@lru_cache(maxsize=8)
def _pack(lang):
    path=PACK_DIR/f'{lang}.json'
    try:
        data=json.loads(path.read_text(encoding='utf8'))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):return {}


def tr(value):
    if not isinstance(value,str):return value
    language=st.session_state.get('rf_interface_lang','en')
    if language not in LANG_CODES or language=='en':return value
    key=value.strip()
    translated=_pack(language).get(key)
    if not translated:
        # Match known f-string templates such as "Page {slot0} of {slot1}".
        # Dynamic values (names, numbers, CV text) stay unchanged.
        for template, localized in _pack(language).items():
            if '{slot' not in template:continue
            parts=re.split(r'(\{slot\d+\})',template)
            regex=''
            for part in parts:
                if re.fullmatch(r'\{slot\d+\}',part):regex+='(.*?)'
                else:regex+=re.escape(part)
            match=re.fullmatch(regex,key,re.DOTALL)
            if match:
                result=localized
                for i,original_value in enumerate(match.groups()):
                    result=result.replace('{slot'+str(i)+'}',original_value)
                translated=result
                break
    if not translated:return value
    return value[:len(value)-len(value.lstrip())]+translated+value[len(value.rstrip()):]


def tr_html(value):
    if not isinstance(value,str):return value
    # Translate ONLY exact HTML text nodes; never attributes, CSS, or CV data.
    return re.sub(r'(?<=>)([^<>]+)(?=<)',
                  lambda m:tr(m.group(1)),value)
