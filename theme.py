"""
Shared dark theme for Poster Tools: a near-black background, violet accent,
and a Manrope/JetBrains Mono type pairing. Call inject() once near the top
of app.py, right after st.set_page_config(). Use eyebrow() for the small
uppercase "kicker" labels above section headings.
"""

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
  --bg: #0a0a0f;
  --bg-panel: #131318;
  --bg-panel-hover: #191921;
  --border: #26262f;
  --border-hover: #3a3a4a;
  --text: #e8e8ec;
  --text-dim: #8b8b99;
  --text-faint: #5c5c6b;
  --accent: #8b5cf6;
  --accent-hover: #a78bfa;
  --accent-dim: rgba(139, 92, 246, 0.14);
  --success: #34d399;
  --warning: #fbbf24;
  --error: #f87171;
  --info: #60a5fa;
}

/* ---------------------------------------------------------------- base */
html, body, .stApp {
  background: var(--bg) !important;
  color: var(--text);
  font-family: 'Manrope', -apple-system, sans-serif;
}

[data-testid="stHeader"] {
  background: transparent !important;
}

[data-testid="stAppViewContainer"] .block-container {
  padding-top: 2.5rem;
  max-width: 900px;
}

h1, h2, h3 {
  font-family: 'Manrope', sans-serif !important;
  font-weight: 800 !important;
  letter-spacing: -0.02em;
  color: var(--text) !important;
}

h1 { font-size: 2.4rem !important; }
h2 { font-size: 1.4rem !important; }
h3 { font-size: 1.15rem !important; }

p, span, label, .stMarkdown, [data-testid="stCaptionContainer"] {
  color: var(--text-dim);
}

/* ---------------------------------------------------------------- eyebrow */
.eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent-hover);
  margin-bottom: 0.6rem;
}
.eyebrow-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
  box-shadow: 0 0 8px var(--accent);
}

/* ---------------------------------------------------------------- tabs */
[data-baseweb="tab-list"] {
  gap: 4px;
  border-bottom: 1px solid var(--border) !important;
}
[data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
  font-family: 'Manrope', sans-serif;
  font-weight: 600;
  font-size: 0.92rem;
}
[data-baseweb="tab"] {
  color: var(--text-faint) !important;
  background: transparent !important;
  padding: 10px 16px !important;
  transition: color 0.15s ease;
}
[data-baseweb="tab"]:hover {
  color: var(--text) !important;
}
[data-baseweb="tab"][aria-selected="true"] {
  color: var(--text) !important;
}
[data-baseweb="tab-highlight"] {
  background-color: var(--accent) !important;
  height: 2px !important;
}
[data-baseweb="tab-border"] {
  background: var(--border) !important;
}

/* ---------------------------------------------------------------- buttons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  font-family: 'Manrope', sans-serif !important;
  font-weight: 700 !important;
  border-radius: 999px !important;
  border: 1px solid var(--border) !important;
  background: transparent !important;
  color: var(--text) !important;
  padding: 0.5rem 1.3rem !important;
  transition: all 0.15s ease !important;
  box-shadow: none !important;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--border-hover) !important;
  background: var(--bg-panel-hover) !important;
  color: var(--text) !important;
}
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
  background: var(--accent) !important;
  border: 1px solid var(--accent) !important;
  color: #fff !important;
}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {
  background: var(--accent-hover) !important;
  border-color: var(--accent-hover) !important;
  transform: translateY(-1px);
  box-shadow: 0 6px 18px var(--accent-dim) !important;
}

/* ---------------------------------------------------------------- inputs */
.stTextInput input,
.stTextArea textarea,
.stNumberInput input {
  background: var(--bg-panel) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  color: var(--text) !important;
  font-family: 'Manrope', sans-serif;
}
.stTextInput input:focus,
.stTextArea textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 1px var(--accent) !important;
}

/* ---------------------------------------------------------------- file uploader */
[data-testid="stFileUploaderDropzone"] {
  background: var(--bg-panel) !important;
  border: 1px dashed var(--border) !important;
  border-radius: 14px !important;
  transition: border-color 0.15s ease;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: var(--accent) !important;
}
[data-testid="stFileUploaderDropzone"] button {
  border-radius: 999px !important;
}

/* ---------------------------------------------------------------- radio / slider */
[data-testid="stRadio"] label {
  color: var(--text) !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
  background-color: var(--accent) !important;
}
[data-testid="stTickBar"] {
  display: none;
}

/* ---------------------------------------------------------------- alerts */
[data-testid="stAlertContainer"], .stAlert {
  border-radius: 12px !important;
  border: 1px solid var(--border) !important;
  background: var(--bg-panel) !important;
}

/* ---------------------------------------------------------------- containers / cards */
[data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {
  gap: 0.4rem;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
  border-radius: 16px !important;
}
[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: var(--border) !important;
  background: var(--bg-panel) !important;
  border-radius: 16px !important;
  transition: border-color 0.15s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
  border-color: var(--border-hover) !important;
}

/* ---------------------------------------------------------------- divider */
hr {
  border-color: var(--border) !important;
}

/* ---------------------------------------------------------------- progress bar */
[data-testid="stProgress"] > div > div > div {
  background: var(--accent) !important;
}

/* ---------------------------------------------------------------- images */
[data-testid="stImage"] img {
  border-radius: 10px;
}

/* ---------------------------------------------------------------- footer / toolbar cleanup */
#MainMenu, footer {
  visibility: hidden;
}
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def eyebrow(text):
    st.markdown(
        f'<div class="eyebrow"><span class="eyebrow-dot"></span>{text}</div>',
        unsafe_allow_html=True,
    )
