"""Shared, in-process public trial request budget for ResumeForge AI.

Best-effort protection only: applies across Streamlit sessions served by this
Python process. Counts reset on process restart and are not shared across
multiple replicas. Groq's organization limits remain the final enforcement.
"""
from __future__ import annotations

from collections import deque
from io import BytesIO
from threading import Lock
from time import monotonic
from urllib.error import HTTPError
from urllib.request import urlopen

import streamlit as st

# Conservative shared PUBLIC TRIAL limits, across chat, review, and translation.
MAX_PER_MINUTE = 5
MAX_PER_HOUR = 45
MAX_PER_DAY = 180
MAX_REQUEST_BYTES = 60000


@st.cache_resource(show_spinner=False)
def _shared_budget():
    # Thread-safe across all users and sessions in one Streamlit process.
    return {"lock": Lock(), "events": deque()}


def _limit_response(request, reason, code=429):
    # Use HTTPError so existing app error handlers can show a safe message.
    message = ('ResumeForge AI public trial limit reached. '
               'Please try again later.' if code == 429 else reason)
    raise HTTPError(
        request.full_url, code, message,
        {"Retry-After": "60"} if code == 429 else {},
        BytesIO(message.encode("utf-8")),
    )


def guarded_urlopen(request, timeout=60):
    """Reserve one shared request slot before contacting Groq.

    Counts attempted requests, including failed requests, to discourage retries
    that exhaust a shared free-tier allowance. Never stores request content.
    """
    if len(request.data or b"") > MAX_REQUEST_BYTES:
        _limit_response(request, "AI request exceeds the allowed size.", 413)

    state = _shared_budget()
    now = monotonic()
    with state["lock"]:
        events = state["events"]
        while events and now - events[0] >= 86400:
            events.popleft()
        minute = sum(now - t < 60 for t in events)
        hour = sum(now - t < 3600 for t in events)
        if minute >= MAX_PER_MINUTE or hour >= MAX_PER_HOUR or len(events) >= MAX_PER_DAY:
            _limit_response(request, "Public AI trial budget exhausted.")
        events.append(now)
    return urlopen(request, timeout=timeout)
