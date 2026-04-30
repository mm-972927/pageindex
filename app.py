import os
import time
import uuid
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from pageindex import (
    pdf_to_pages,
    build_toc_tree,
    retrieve_and_answer,
    tree_to_display_string,
    flatten_nodes,
)
from observability import trace_index, QueryTrace, is_enabled

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PageIndex Doc QA",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bitter:wght@400;600;700&family=JetBrains+Mono:wght@400;500&family=Nunito:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Nunito', sans-serif; }

.stApp {
    background: #f7f4ef;
    color: #1a1410;
}

section[data-testid="stSidebar"] {
    background: #1e1b16;
    border-right: none;
}
section[data-testid="stSidebar"] * { color: #c8bfb0 !important; }
section[data-testid="stSidebar"] .stButton > button {
    background: #2e2920 !important;
    border: 1px solid #3d3528 !important;
    color: #e8c87a !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #3d3528 !important;
    border-color: #e8c87a !important;
}

/* Header */
.app-header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 4px;
}
.app-title {
    font-family: 'Bitter', serif;
    font-size: 1.7rem;
    font-weight: 700;
    color: #1a1410;
    letter-spacing: -0.5px;
}
.app-subtitle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: #9a8870;
    background: #ede8e0;
    border: 1px solid #d8cfc0;
    border-radius: 4px;
    padding: 2px 8px;
}

/* Upload area */
.stFileUploader > div {
    background: #fff !important;
    border: 2px dashed #c8b898 !important;
    border-radius: 12px !important;
}

/* Phase cards */
.phase-card {
    background: #fff;
    border: 1px solid #e0d8cc;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 8px 0;
}
.phase-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 6px;
}
.phase-label.toc { color: #6b7fa3; }
.phase-label.retrieve { color: #8a6b3a; }
.phase-label.answer { color: #4a7a5a; }

/* Node badge */
.node-tag {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    background: #f0ece4;
    border: 1px solid #d0c8b8;
    border-radius: 5px;
    padding: 2px 7px;
    margin: 2px;
    color: #5a4a30;
}
.node-tag.primary {
    background: #e8c87a22;
    border-color: #e8c87a;
    color: #8a6000;
}

/* Chat */
.user-msg {
    background: #fff;
    border: 1px solid #e0d8cc;
    border-radius: 10px 10px 4px 10px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 0.9rem;
    color: #1a1410;
}
.assistant-msg {
    background: #1e1b16;
    border-radius: 4px 10px 10px 10px;
    padding: 14px 18px;
    margin: 8px 0;
    font-size: 0.9rem;
    color: #d4cbbf;
    line-height: 1.7;
}

/* ToC tree */
.toc-display {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    background: #fff;
    border: 1px solid #e0d8cc;
    border-radius: 8px;
    padding: 14px;
    white-space: pre-wrap;
    color: #5a4a30;
    line-height: 1.7;
    max-height: 380px;
    overflow-y: auto;
}

/* Stats row */
.stats-row {
    display: flex;
    gap: 10px;
    margin: 10px 0;
}
.stat-pill {
    background: #fff;
    border: 1px solid #e0d8cc;
    border-radius: 20px;
    padding: 5px 14px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #5a4a30;
}
.stat-pill span { color: #e8a020; font-weight: 600; }

/* Meta line */
.meta-line {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #b0a080;
    margin-top: 5px;
}

/* Buttons */
.stButton > button {
    background: #1e1b16;
    border: none;
    color: #e8c87a;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    border-radius: 8px;
    padding: 8px 20px;
    transition: all 0.15s;
}
.stButton > button:hover {
    background: #2e2920;
}

/* Input */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: #fff !important;
    border: 1px solid #d0c8b8 !important;
    border-radius: 8px !important;
    color: #1a1410 !important;
    font-family: 'Nunito', sans-serif !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #e8a020 !important;
    box-shadow: 0 0 0 2px #e8a02022 !important;
}

/* Progress */
.stProgress > div > div > div { background: #e8a020 !important; }

/* Divider */
hr { border-color: #e0d8cc !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #f7f4ef; }
::-webkit-scrollbar-thumb { background: #d0c8b8; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ── Session init ───────────────────────────────────────────────────────────────
def init():
    defaults = {
        "session_id": str(uuid.uuid4())[:8],
        "pages": None,
        "toc_tree": None,
        "doc_name": "",
        "messages": [],
        "chat_history": [],
        "total_tokens": 0,
        "total_queries": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init()


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="margin-bottom:20px;">
        <div style="font-family:'Bitter',serif; font-size:1.2rem; font-weight:700; color:#e8c87a;">📑 PageIndex</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:0.65rem; color:#6a5a40; margin-top:3px;">
            vectorless · reasoning-based RAG
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Upload Document**")

    uploaded = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        label_visibility="collapsed"
    )

    if uploaded:
        if st.button("⚡ Index Document", use_container_width=True):
            with st.spinner("Reading pages..."):
                try:
                    file_bytes = uploaded.read()
                    pages = pdf_to_pages(file_bytes)
                    st.session_state.pages = pages
                    st.session_state.doc_name = uploaded.name

                    st.success(f"✓ {len(pages)} pages loaded")
                except Exception as e:
                    st.error(f"PDF error: {e}")
                    st.stop()

            with st.spinner("Building ToC tree..."):
                try:
                    t0 = time.time()
                    toc_tree, idx_stats = build_toc_tree(pages)
                    idx_latency = round(time.time() - t0, 2)
                    st.session_state.toc_tree = toc_tree
                    st.session_state.messages = []
                    st.session_state.chat_history = []
                    st.session_state.total_tokens = 0
                    st.session_state.total_queries = 0

                    total_nodes = len(flatten_nodes(toc_tree))
                    st.success(f"✓ {total_nodes} nodes indexed")

                    # Langfuse — index trace
                    trace_index(
                        session_id=st.session_state.session_id,
                        doc_name=uploaded.name,
                        total_pages=len(pages),
                        total_nodes=total_nodes,
                        tokens=idx_stats["tokens"],
                        latency_sec=idx_stats["latency_sec"],
                    )
                except Exception as e:
                    st.error(f"Tree build error: {e}")

    # Stats
    if st.session_state.toc_tree:
        st.markdown("---")
        pages_count = len(st.session_state.pages) if st.session_state.pages else 0
        nodes_count = len(flatten_nodes(st.session_state.toc_tree))

        st.markdown(f"""
        <div style="font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#6a5a40; line-height:2.2;">
            📄 &nbsp;{st.session_state.doc_name[:28]}<br>
            📃 &nbsp;<span style="color:#e8c87a;">{pages_count}</span> pages<br>
            🌲 &nbsp;<span style="color:#e8c87a;">{nodes_count}</span> ToC nodes<br>
            💬 &nbsp;<span style="color:#e8c87a;">{st.session_state.total_queries}</span> queries<br>
            🔢 &nbsp;<span style="color:#e8c87a;">{st.session_state.total_tokens:,}</span> tokens
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🗑 Clear", use_container_width=True):
            for k in ["pages","toc_tree","doc_name","messages","chat_history","total_tokens","total_queries"]:
                st.session_state[k] = None if k in ["pages","toc_tree"] else ([] if k in ["messages","chat_history"] else ("" if k=="doc_name" else 0))
            st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace; font-size:0.62rem; color:#4a3a20; line-height:2;">
        <b style="color:#6a5a40;">How it works</b><br>
        1. PDF → pages list<br>
        2. LLM builds ToC tree<br>
        3. Query → LLM reasons over ToC<br>
        4. Retrieve matched page(s)<br>
        5. LLM generates answer<br>
        <br>
        No vectors. No embeddings.<br>
        Pure structure + reasoning.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    lf_color = "#4caf7d" if is_enabled() else "#6a5a40"
    lf_label = "● Langfuse ON" if is_enabled() else "○ Langfuse OFF"
    st.markdown(
        f'<div style="font-family:JetBrains Mono,monospace; font-size:0.68rem; color:{lf_color};">'
        f'{lf_label}</div>'
        f'<div style="font-family:JetBrains Mono,monospace; font-size:0.6rem; color:#3a2a10; margin-top:2px;">'
        f'cloud.langfuse.com</div>',
        unsafe_allow_html=True,
    )


# ── Main ───────────────────────────────────────────────────────────────────────

if not st.session_state.toc_tree:
    # Landing
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; padding:70px 0 30px;">
            <div style="font-size:3rem; margin-bottom:16px;">📑</div>
            <div style="font-family:'Bitter',serif; font-size:1.6rem; font-weight:700; color:#1a1410; margin-bottom:10px;">
                PageIndex Document Q&A
            </div>
            <div style="color:#7a6a50; font-size:0.9rem; line-height:1.8; max-width:460px; margin:0 auto;">
                Upload a PDF — the system builds a hierarchical <b>Table of Contents tree</b>,
                then answers your questions by <b>reasoning over the tree</b> to find the right pages.
                No vectors. No chunking. No approximate search.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="display:flex; gap:10px; justify-content:center; flex-wrap:wrap; margin-top:10px;">
            <div style="background:#fff; border:1px solid #e0d8cc; border-radius:8px; padding:14px 20px; width:160px; text-align:center;">
                <div style="font-size:1.4rem;">📄</div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:0.68rem; color:#9a8870; margin:4px 0;">STEP 1</div>
                <div style="font-size:0.8rem; font-weight:600; color:#1a1410;">Upload PDF</div>
                <div style="font-size:0.72rem; color:#7a6a50;">Any document</div>
            </div>
            <div style="background:#fff; border:1px solid #e0d8cc; border-radius:8px; padding:14px 20px; width:160px; text-align:center;">
                <div style="font-size:1.4rem;">🌲</div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:0.68rem; color:#9a8870; margin:4px 0;">STEP 2</div>
                <div style="font-size:0.8rem; font-weight:600; color:#1a1410;">Build ToC Tree</div>
                <div style="font-size:0.72rem; color:#7a6a50;">Hierarchical index</div>
            </div>
            <div style="background:#fff; border:1px solid #e0d8cc; border-radius:8px; padding:14px 20px; width:160px; text-align:center;">
                <div style="font-size:1.4rem;">🔍</div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:0.68rem; color:#9a8870; margin:4px 0;">STEP 3</div>
                <div style="font-size:0.8rem; font-weight:600; color:#1a1410;">Ask Anything</div>
                <div style="font-size:0.72rem; color:#7a6a50;">Reasoning retrieval</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

else:
    # Main interface: left = chat, right = ToC tree
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown(f"""
        <div class="app-header">
            <span class="app-title">{st.session_state.doc_name}</span>
            <span class="app-subtitle">PageIndex · Vectorless RAG</span>
        </div>
        <div class="stats-row">
            <div class="stat-pill"><span>{len(st.session_state.pages)}</span> pages</div>
            <div class="stat-pill"><span>{len(flatten_nodes(st.session_state.toc_tree))}</span> nodes</div>
            <div class="stat-pill"><span>{st.session_state.total_queries}</span> queries</div>
            <div class="stat-pill"><span>{st.session_state.total_tokens:,}</span> tokens</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # Chat history
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(f'<div class="user-msg">💬 {msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="assistant-msg">{msg["content"]}</div>', unsafe_allow_html=True)

                # Reasoning trace expander
                if msg.get("nodes_read") or msg.get("reasoning"):
                    with st.expander("🔍 Retrieval trace", expanded=False):
                        if msg.get("reasoning"):
                            st.markdown(f"""
                            <div class="phase-card">
                                <div class="phase-label retrieve">Reasoning</div>
                                <div style="font-size:0.82rem; color:#5a4a30; line-height:1.6;">{msg['reasoning']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        if msg.get("nodes_read"):
                            nodes_html = ""
                            for n in msg["nodes_read"]:
                                cls = "primary" if n.get("is_primary") else ""
                                nodes_html += f'<span class="node-tag {cls}">[{n["node_id"]}] p.{n["page_index"]+1} {n["title"][:35]}</span>'
                            st.markdown(f"""
                            <div class="phase-card">
                                <div class="phase-label toc">Nodes Retrieved</div>
                                {nodes_html}
                            </div>
                            """, unsafe_allow_html=True)

                if msg.get("meta"):
                    m = msg["meta"]
                    st.markdown(
                        f'<div class="meta-line">⚡ {m.get("nodes",0)} nodes · {m.get("tokens",0)} tokens · {m.get("latency",0)}s</div>',
                        unsafe_allow_html=True
                    )

        # Input
        st.markdown("---")
        query = st.text_area(
            "Ask",
            placeholder="Ask any question about the document...",
            height=80,
            label_visibility="collapsed",
            key="query_box"
        )
        ask_col, _ = st.columns([1, 5])
        with ask_col:
            ask_btn = st.button("Ask →", use_container_width=True)

        if ask_btn and query.strip():
            st.session_state.messages.append({"role": "user", "content": query.strip()})

            with st.spinner("🧠 Reasoning over ToC..."):
                t0 = time.time()
                try:
                    qt = QueryTrace(
                        session_id=st.session_state.session_id,
                        doc_name=st.session_state.doc_name,
                        query=query.strip(),
                    )
                    result = retrieve_and_answer(
                        query=query.strip(),
                        toc_tree=st.session_state.toc_tree,
                        pages=st.session_state.pages,
                        chat_history=st.session_state.chat_history,
                        trace=qt,
                    )
                    latency = round(time.time() - t0, 2)
                    qt.finish(
                        answer=result["answer"],
                        total_tokens=result["tokens"],
                        nodes_read=len(result["nodes_read"]),
                    )

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "reasoning": result["reasoning"],
                        "nodes_read": result["nodes_read"],
                        "meta": {
                            "nodes": len(result["nodes_read"]),
                            "tokens": result["tokens"],
                            "latency": latency,
                        }
                    })

                    st.session_state.chat_history.append({"role": "user", "content": query.strip()})
                    st.session_state.chat_history.append({"role": "assistant", "content": result["answer"]})
                    st.session_state.total_tokens += result["tokens"]
                    st.session_state.total_queries += 1

                except Exception as e:
                    st.error(f"Error: {e}")

            st.rerun()

    with right:
        st.markdown("""
        <div style="font-family:'JetBrains Mono',monospace; font-size:0.68rem; color:#9a8870;
                    text-transform:uppercase; letter-spacing:1px; margin-bottom:8px;">
            Table of Contents Tree
        </div>
        """, unsafe_allow_html=True)

        toc_str = tree_to_display_string(st.session_state.toc_tree)
        st.markdown(f'<div class="toc-display">{toc_str}</div>', unsafe_allow_html=True)

        all_nodes = flatten_nodes(st.session_state.toc_tree)
        st.markdown(f"""
        <div style="margin-top:10px; font-family:'JetBrains Mono',monospace; font-size:0.65rem; color:#9a8870;">
            {len(all_nodes)} total nodes across {len(st.session_state.toc_tree)} top-level sections
        </div>
        """, unsafe_allow_html=True)