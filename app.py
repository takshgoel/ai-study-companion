import io
import os

import streamlit as st
from docx import Document
from dotenv import load_dotenv
from openai import OpenAI
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from streamlit_javascript import st_javascript

from ai.embeddings import get_vector_store
from ai.rag_pipeline import build_context_for_question, generate_study_guide
from ai.tutor_logic import generate_tutor_reply
from components.chat_panel import render_chat_panel
from components.sidebar import render_sidebar_panel
from components.study_guide import render_study_guide_panel
from utils.anchor_utils import add_anchor_links, normalize_study_guide
from utils.file_parser import parse_uploaded_file

# -------------------------------------------------
# APP INIT
# -------------------------------------------------

st.set_page_config(layout="wide", page_title="AI Lecture Study Companion")

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if "docs" not in st.session_state:
    st.session_state.docs = {}
if "guide" not in st.session_state:
    st.session_state.guide = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "selected_text" not in st.session_state:
    st.session_state.selected_text = ""
if "vector_store" not in st.session_state:
    st.session_state.vector_store = {"index": None, "chunks": [], "metadata": []}
if "docs_signature" not in st.session_state:
    st.session_state.docs_signature = ()

# -------------------------------------------------
# STYLES
# -------------------------------------------------

st.markdown(
    """
<style>
:root {
  --bg: #f5f5f5;
  --panel: #ffffff;
  --text: #111111;
  --muted: #5f5f5f;
  --line: rgba(0, 0, 0, 0.14);
  --danger: #bb2020;
}

html, body, [class*="css"] {
  font-family: "Inter", "Segoe UI", sans-serif;
}

.stApp {
  background: linear-gradient(180deg, #ffffff 0%, var(--bg) 100%);
  color: var(--text);
}

[data-testid="stHeader"], #MainMenu, footer {
  visibility: hidden;
}

[data-testid="stAppViewContainer"] {
  overflow: hidden;
}

.main-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 62px;
  z-index: 100;
  display: flex;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.97);
}

.main-header-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text);
}

.main-header-sub {
  color: var(--muted);
  font-size: 0.88rem;
}

.block-container {
  padding-top: 78px !important;
  padding-bottom: 10px !important;
  max-width: 100% !important;
}

[data-testid="stFileUploaderDropzone"] {
  border: 1px dashed #8e8e8e !important;
  background: #fafafa;
  border-radius: 14px;
}

[data-testid="stFileUploaderDropzone"] section {
  padding: 1rem 0.8rem;
}

[data-testid="stFileUploaderDropzone"] button {
  background: #111111 !important;
  color: #ffffff !important;
  border: 1px solid #111111 !important;
}

[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploaderDropzone"] button:focus,
[data-testid="stFileUploaderDropzone"] button:active {
  background: #111111 !important;
  color: #ffffff !important;
  border: 1px solid #111111 !important;
}

[data-testid="stDownloadButton"] button {
  background: #111111 !important;
  color: #ffffff !important;
  border: 1px solid #111111 !important;
}

[data-testid="stDownloadButton"] button:hover,
[data-testid="stDownloadButton"] button:focus,
[data-testid="stDownloadButton"] button:active {
  background: #111111 !important;
  color: #ffffff !important;
  border: 1px solid #111111 !important;
}

[data-testid="stFileUploaderFile"] {
  background: #ffffff !important;
  border: 1px solid rgba(0, 0, 0, 0.16) !important;
}

[data-testid="stFileUploaderFileName"] {
  color: #111111 !important;
}

.panel-title {
  font-size: 1rem;
  font-weight: 700;
  margin-bottom: 0.2rem;
  color: var(--text);
}

.panel-sub {
  color: var(--muted);
  font-size: 0.86rem;
  margin-bottom: 0.75rem;
}

[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
}

[data-testid="stChatMessage"] {
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 10px;
}

[data-testid="stButton"] button {
  background: #ffffff !important;
  color: #111111 !important;
  border: 1px solid rgba(0, 0, 0, 0.24) !important;
}

[data-testid="stButton"] button:hover {
  background: #f3f3f3 !important;
}

[data-testid="stButton"] button[kind="primary"] {
  background: var(--danger) !important;
  border: 1px solid #8f1a1a !important;
  color: #ffffff !important;
}

[data-testid="stButton"] button[kind="primary"]:hover {
  background: #9f1c1c !important;
}

hr {
  border-color: var(--line);
}
</style>

<div class="main-header">
  <div>
    <div class="main-header-title">AI Study Companion</div>
    <div class="main-header-sub">Upload lectures, generate structured notes, and learn with your tutor.</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

status_placeholder = st.empty()

# -------------------------------------------------
# EXPORT HELPERS
# -------------------------------------------------


def create_word_doc(text: str):
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer



def create_pdf(text: str):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    _, height = letter
    y = height - 40

    for line in text.split("\n"):
        if y < 40:
            c.showPage()
            y = height - 40
        c.drawString(40, y, line[:110])
        y -= 15

    c.save()
    buffer.seek(0)
    return buffer


# -------------------------------------------------
# FILE + VECTOR STATE
# -------------------------------------------------


def current_docs_list() -> list[dict]:
    docs = list(st.session_state.docs.values())
    docs.sort(key=lambda x: x["name"].lower())
    return docs



def docs_signature(docs: list[dict]) -> tuple:
    return tuple((doc["id"], doc["name"], len(doc["content"])) for doc in docs)


# -------------------------------------------------
# LAYOUT
# -------------------------------------------------

sidebar_col, study_col, tutor_col = st.columns([1.35, 1.85, 1.1], gap="medium")

with sidebar_col:
    sidebar_event = render_sidebar_panel()

# Process newly uploaded files
new_upload_added = False
for uploaded in sidebar_event["uploaded_files"] or []:
    parsed = parse_uploaded_file(uploaded)
    if not parsed["ok"]:
        st.error(parsed["error"])
        continue

    already_present = parsed["id"] in st.session_state.docs
    st.session_state.docs[parsed["id"]] = parsed
    if not already_present:
        new_upload_added = True

if new_upload_added:
    st.rerun()

# Remove file if requested
if sidebar_event["remove_file_id"]:
    removed = st.session_state.docs.pop(sidebar_event["remove_file_id"], None)
    if removed:
        st.info(f"Removed {removed['name']}")

# Update vector store only when doc set changes
all_docs = current_docs_list()
signature = docs_signature(all_docs)
if signature != st.session_state.docs_signature:
    if all_docs:
        with status_placeholder:
            with st.spinner("Processing slides and building knowledge base..."):
                try:
                    st.session_state.vector_store = get_vector_store(all_docs)
                except Exception as exc:
                    st.session_state.vector_store = {"index": None, "chunks": [], "metadata": []}
                    st.error(f"Vector store error: {exc}")
        status_placeholder.empty()
    else:
        st.session_state.vector_store = {"index": None, "chunks": [], "metadata": []}
    st.session_state.docs_signature = signature

# Generate study guide with percentage progress
if sidebar_event["generate_clicked"]:
    if not all_docs:
        st.error("Upload at least one PDF or PPTX file before generating the study guide.")
    else:
        try:
            with status_placeholder:
                progress_bar = st.progress(0, text="0% - Starting guide generation...")

                def on_progress(done: int, total: int, message: str):
                    pct = min(100, int((done / max(1, total)) * 100))
                    progress_bar.progress(pct, text=f"{pct}% - {message}")

                raw_guide = generate_study_guide(
                    client,
                    all_docs,
                    sidebar_event["additional_context"],
                    progress_callback=on_progress,
                )
                progress_bar.progress(100, text="100% - Finalizing guide...")

            status_placeholder.empty()
            normalized = normalize_study_guide(raw_guide)
            st.session_state.guide = add_anchor_links(normalized)
            st.success("Study guide ready.")
        except Exception as exc:
            status_placeholder.empty()
            st.error(f"Could not generate study guide: {exc}")

with study_col:
    st.markdown('<div class="panel-title">Study Guide</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-sub">Focused reading workspace</div>', unsafe_allow_html=True)
    render_study_guide_panel(st.session_state.guide)

    if st.session_state.guide:
        selected_text = st_javascript("window.getSelection().toString();")
        if selected_text and len(selected_text) > 5:
            if st.button("Ask AI about highlighted text", use_container_width=False):
                st.session_state.selected_text = selected_text
                st.rerun()

        export_row = st.columns(2)
        export_row[0].download_button(
            "Download Word",
            data=create_word_doc(st.session_state.guide),
            file_name="study_guide.docx",
            use_container_width=True,
        )
        export_row[1].download_button(
            "Download PDF",
            data=create_pdf(st.session_state.guide),
            file_name="study_guide.pdf",
            use_container_width=True,
        )

with tutor_col:
    st.markdown('<div class="panel-title">AI Tutor</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-sub">Ask questions and get guided explanations</div>', unsafe_allow_html=True)
    user_question = render_chat_panel()

    if user_question:
        st.session_state.chat_history.append({"role": "user", "content": user_question})

        try:
            context_text = build_context_for_question(user_question, st.session_state.vector_store)
            answer = generate_tutor_reply(
                client=client,
                question=user_question,
                selected_text=st.session_state.selected_text,
                context_text=context_text,
                chat_history=st.session_state.chat_history,
            )
        except Exception as exc:
            answer = f"### Explanation\nI hit an error while generating a response.\n\n### Example\nPlease try again in a moment.\n\n### Simplified Version\nError details: {exc}"

        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()