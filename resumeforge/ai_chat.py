
"""ResumeForge AI Assistant — Groq-powered chat."""

from resumeforge.i18n import tr, tr_html
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st
from resumeforge.public_limit import guarded_urlopen
from resumeforge.hr_expert import build_hr_prompt

MODEL = "openai/gpt-oss-20b"

SYSTEM_PROMPT = """
You are ResumeForge AI Assistant, a professional CV writing coach.

Help users write clear, credible, ATS-friendly CVs.
Improve professional summaries, experience descriptions,
skills sections, and job-specific wording.

Rules:
- Never invent experience, qualifications, employers, or results.
- Ask for missing facts instead of making them up.
- Keep suggestions concise, specific, and professional.
- Explain proposed improvements when helpful.
- Never claim you have modified the user's CV.
- Never request passwords or sensitive credentials.
"""


def ai_assistant_page():
    st.title(tr("ResumeForge AI Assistant"))

    st.caption(
        tr("Your personal CV writing assistant · Powered by Groq")
    )

    st.info(
        tr("Messages you submit are processed by Groq. "
        "Only share CV information you are comfortable sending "
        "to this external AI service.")
    )

    consent = st.checkbox(
        tr("I understand and agree to send my chat messages to Groq."),
        key="rf_ai_consent",
    )

    if not consent:
        return

    if "rf_ai_chat" not in st.session_state:
        st.session_state.rf_ai_chat = []

    if "rf_ai_calls" not in st.session_state:
        st.session_state.rf_ai_calls = []

    if st.button(tr("Clear conversation"), key="rf_ai_clear"):
        st.session_state.rf_ai_chat = []
        st.rerun()

    if not st.session_state.rf_ai_chat:
        st.markdown(
            tr("**Welcome!** I can help strengthen your CV, "
            "rewrite a professional summary, or tailor your "
            "experience to a job description.")
        )

    for message in st.session_state.rf_ai_chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input(
        tr("Ask ResumeForge AI about your CV...")
    )

    if not prompt:
        return

    if len(prompt) > 2500:
        st.warning(tr("Please keep your message under 2,500 characters."))
        return

    now = time.time()

    st.session_state.rf_ai_calls = [
        call_time
        for call_time in st.session_state.rf_ai_calls
        if now - call_time < 600
    ]

    if len(st.session_state.rf_ai_calls) >= 5:
        st.warning(
            tr("This chat session has reached its temporary usage limit. "
            "Please try again later.")
        )
        return

    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        st.error(tr("The AI service has not been configured."))
        return

    st.session_state.rf_ai_chat.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(tr("Preparing your response...")):

            payload = {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": build_hr_prompt(prompt)},
                    *st.session_state.rf_ai_chat[-10:],
                ],
                "max_completion_tokens": 900,
            }

            request = Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "ResumeForge/1.0",
                },
                method="POST",
            )

            st.session_state.rf_ai_calls.append(now)

            try:
                with guarded_urlopen(request, timeout=45) as response:
                    result = json.load(response)

                answer = result["choices"][0]["message"]["content"]

                if not answer:
                    raise ValueError("Empty AI response")

            except HTTPError as error:
                st.error(
                    tr(f"AI service error ({error.code}). "
                    "Please try again later.")
                )
                st.session_state.rf_ai_chat.pop()
                return

            except (URLError, TimeoutError, ValueError, KeyError, IndexError):
                st.error(
                    tr("Unable to retrieve an AI response. "
                    "Please try again later.")
                )
                st.session_state.rf_ai_chat.pop()
                return

            st.markdown(answer)

            st.session_state.rf_ai_chat.append(
                {"role": "assistant", "content": answer}
            )
