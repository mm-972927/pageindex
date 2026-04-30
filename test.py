# from dotenv import load_dotenv
# load_dotenv()
# from langfuse import Langfuse

# lf = Langfuse()
# t = lf.trace(name="test_trace", input={"test": "hello"})
# lf.flush()
# print("SUCCESS — check Langfuse now")


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

with st.sidebar:
    st.markdown("""
    <div style="margin-bottom:20px;">
        <div style="font-family:'Bitter',serif; font-size:1.2rem; font-weight:700; color:#e8c87a;">📑 PageIndex</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:0.65rem; color:#6a5a40; margin-top:3px;">
            vectorless · reasoning-based RAG
        </div>
    </div>
    """, unsafe_allow_html=True)