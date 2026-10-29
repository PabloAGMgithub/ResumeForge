# ResumeForge Studio

A **free, local-first** CV manager with two custom HTML/CSS templates reconstructed from reference PDFs:

- **Executive** — A4, charcoal left sidebar, professional portrait, subdued AI-brain illustration, navy content, four competence panels, and detailed history.
- **Harvard-style** — US Letter, centered contact header, burgundy headings and job rails, **rounded skill pills made of actual text**, and two-column light-gray project cards. No portrait.

The aim is faithful reproduction, not replacing these designs with generic resume themes. Exported PDFs use selectable text.

## Start locally

1. Install **Python 3.11+**.
2. Extract this project ZIP to a folder on your computer.
3. Open a terminal in that folder and run:

   **Windows (PowerShell):**
   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m streamlit run app.py
   ```

   **macOS/Linux:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   python -m streamlit run app.py
   ```

4. Streamlit will show a local address such as `http://localhost:8501`. You do not need an API key to import, edit, preview, or export CVs.

**PDF Generation — Windows, macOS, and Linux**

ResumeForge 2.0 uses **Playwright with Chromium** to generate professional, selectable-text PDF documents from HTML/CSS templates.

Unlike WeasyPrint, this approach does not require manually installing Pango or MSYS2 on Windows.

After installing the Python dependencies, install Chromium:

```bash
python -m playwright install chromium
```

Then launch ResumeForge:

```bash
python -m streamlit run app.py
```

**Font compatibility:** ResumeForge uses Carlito where available, with Calibri and Arial as fallback fonts. Font availability may slightly affect text spacing, line wrapping, and pagination.

**Cloud deployment:** Linux hosting environments may require additional Chromium system dependencies. These must be configured when deploying ResumeForge to Streamlit Community Cloud.

## Use it

1. **Import CV:** Upload a PDF, DOCX, or exported ResumeForge JSON. The initial PDF/DOCX extraction is conservative. CVs with complex columns or image-based text require a manual review of the "Additional information" field.
2. **My Information:** Edit every section, including jobs and their separate bullets; add/remove rows. This edits a **working copy**, leaving the master unchanged.
3. **Target & AI:** Paste a job description to see basic keyword overlap. Optionally connect an OpenAI-compatible chat/completions endpoint with your own temporary key. Only an explicit, consented click sends text. Suggestions are never applied automatically.
4. **Templates:** Choose Executive or Harvard. In Executive, upload/change a photograph or sidebar illustration.
5. **Preview & Export:** Inspect every actual PDF page, then download the PDF and working-profile JSON. A master-profile JSON is also downloadable from the sidebar.

## Privacy and GitHub

- **Never push your private resume JSON, headshot, API keys, or actual exported CVs to a public repository.** `.gitignore` excludes `local_data/`, exported PDFs/DOCX, and Streamlit secrets.
- The starter includes your **personal local profile and photo under `local_data/`** solely for local testing. Those files are excluded from Git. The `examples/demo_cv.json` is fictional and safe to show in the public demo.
- Uploaded content and temporary API keys are kept in the session; don't enable local disk saving on public hosting. Streamlit hosting necessarily receives uploaded content in its app server's memory.
- For durable profile storage, **download the JSON** and re-import it later. Future versions can add browser-based persistence or encrypted local storage.
- A public Streamlit Community Cloud demonstration can run using only `examples/demo_cv.json` and the nonpersonal template artwork. Connect your GitHub repository when the local version is validated.

## Architecture

```text
app.py                        Streamlit UI
resumeforge/model.py          Canonical editable profile schema
resumeforge/importer.py       PDF/DOCX first-pass extraction + source preservation
resumeforge/render.py         HTML templating, print pagination, PDF rendering
resumeforge/ai.py             Opt-in compatible model rewriting
assets/ai_brain_art.png       Executive illustration
local_data/                   Your private profile and photograph (GITIGNORED)
examples/demo_cv.json         Fictional public demo
run_checks.py                 Smoke tests for content and generated PDFs
templates/harvard.html        Harvard-style document structure
templates/harvard.css         Burgundy rules, chips, project cards
templates/executive.html      Executive three-page document structure
templates/executive.css       Dark sidebar, AI art, credential panels
```

## Current functionality and honest limits

**Working in this starter:** HTML/CSS designs, PDF rendering, two exact paper sizes, selectable text, editing, JSON master/working copies, optional photo/art, reference CV local data, extraction transcript, basic parsing, relevance hints, and opt-in AI rewriting.

**To improve after visual validation:** More accurate general-purpose import/classification from heterogeneous PDFs; OCR for scanned PDFs; a richer drag/drop editor; robust pagination for unusually lengthy sections; exact pixel-by-pixel template calibration; DOCX export; personalized public/demo separation with authenticated storage. An input PDF is not a reliable structured-data format, so a full review step is intentional.

## Local tests

```bash
python run_checks.py
```

This renders both templates from the saved master profile and checks page counts, that the PDF has selectable text and that text-based skills appear in the Harvard output.

## License/credit

The layouts and AI artwork included in this starter reflect user-provided design references. Refrain from placing a personal headshot or private contact details in a public repository. A dedicated LICENSE file can be chosen at publication time.
