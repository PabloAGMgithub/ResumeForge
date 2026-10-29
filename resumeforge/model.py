"""Data model and round-trip helpers; no private information is stored automatically."""
from copy import deepcopy


def empty_profile():
    return {
        "name": "", "headline": "", "tagline": "", "location": "",
        "email": "", "phone": "", "linkedin": "", "github": "",
        "summary": "", "skills": [], "skill_groups": [],
        "experience": [], "education": [], "projects": [],
        "training": [], "languages": [], "extra_notes": "",
        "raw_source_text": "", "source_file": "",
    }


def normalize_profile(raw):
    data = empty_profile()
    for k in data:
        if k in raw and isinstance(raw[k], type(data[k])):
            data[k] = deepcopy(raw[k])
    for key in ("skills", "skill_groups", "experience", "education", "projects", "training", "languages"):
        data[key] = [v for v in data[key] if v is not None]
    # Keep custom keys instead of silently dropping possible imported metadata.
    for k, v in raw.items():
        if k not in data:
            data[k] = v
    return data


def flatten_skills(profile):
    if profile.get("skills"):
        return list(dict.fromkeys(str(s).strip() for s in profile["skills"] if str(s).strip()))
    result = []
    for group in profile.get("skill_groups", []):
        result.extend(group.get("items", []))
    return list(dict.fromkeys(x for x in result if x))
