"""Optional, explicit opt-in rewriting; no API request is made on import or preview."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def suggest_rewrite(original: str, target_role: str, job_description: str,
                    endpoint: str, model: str, api_key: str):
    """OpenAI-compatible chat/completions endpoint; returns an *unapplied* suggestion."""
    if not endpoint.lower().startswith("https://") and not endpoint.lower().startswith("http://localhost"):
        raise ValueError("Use a trusted HTTPS endpoint or localhost.")
    if not original.strip() or not model.strip() or not api_key.strip():
        raise ValueError("Provide original content, a model name, and your API key.")
    system = (
        "You are a careful CV editor. Rewrite only the supplied claim to be concise and relevant "
        "to the target job. Preserve the exact meaning and all numeric facts. "
        "Do not invent duties, achievements, metrics, credentials, technologies, or experience. "
        "If insufficient evidence exists, do not add any new details. Return only the revised wording."
    )
    user = (f"ORIGINAL CV CONTENT:\n{original}\n\nTARGET ROLE:\n{target_role}\n\n"
            f"JOB DESCRIPTION (optional):\n{job_description[:4500]}")
    body = json.dumps({"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"temperature":0.2,"max_tokens":350}).encode()
    req=Request(endpoint, data=body, headers={"Authorization": f"Bearer {api_key}",
                                            "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=35) as response:
            data=json.load(response)
        return data["choices"][0]["message"]["content"].strip()
    except (HTTPError, URLError, KeyError, IndexError) as exc:
        raise RuntimeError(f"The model request failed: {exc}") from exc
