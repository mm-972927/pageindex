"""
PageIndex Core — faithful to pageindex_RAG_simple.ipynb
Steps:
  1. Split PDF into pages (list of text strings)
  2. Build hierarchical ToC tree via LLM (node_id, title, summary, page range)
  3. Retrieve: LLM reasons over ToC → selects node_id → fetch page content
  4. Answer: LLM generates answer from retrieved context
"""

import os
import re
import json
import io
import time
from openai import OpenAI

# ── Gemini via OpenAI-compatible endpoint ──────────────────────────────────────
# Get a free API key at: https://aistudio.google.com/apikey
# client = OpenAI(
#     api_key=os.getenv("GEMINI_API_KEY"),
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
# )
# MODEL = "gemini-2.0-flash-lite"

from groq import Groq
client_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# def _call(system: str, messages: list[dict], max_tokens: int = 1000) -> tuple[str, int, int]:
#     """
#     Thin wrapper — returns (text, tokens_in, tokens_out).
#     """
#     resp = client.chat.completions.create(
#         model=MODEL,
#         max_tokens=max_tokens,
#         messages=[{"role": "system", "content": system}] + messages,
#     )
#     text = resp.choices[0].message.content or ""
#     tok_in  = resp.usage.prompt_tokens     if resp.usage else 0
#     tok_out = resp.usage.completion_tokens if resp.usage else 0
#     return text.strip(), tok_in, tok_out

def _call(system: str, messages: list[dict], max_tokens: int = 1000) -> tuple[str, int, int]:
    resp = client_groq.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}] + messages,
    )
    text = resp.choices[0].message.content or ""
    tok_in  = resp.usage.prompt_tokens
    tok_out = resp.usage.completion_tokens
    return text.strip(), tok_in, tok_out


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: PDF → pages
# ─────────────────────────────────────────────────────────────────────────────

def pdf_to_pages(file_bytes: bytes) -> list[str]:
    """
    Extract text from each PDF page.
    Returns list of strings, one per page.
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            text = re.sub(r"\s+", " ", text).strip()
            pages.append(text)
        return pages
    except Exception as e:
        raise RuntimeError(f"PDF parsing failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Build ToC tree
# The tree nodes use page_index (int) instead of char offsets — 
# exactly as in the official notebook
# ─────────────────────────────────────────────────────────────────────────────

TOC_SYSTEM = """You are a document indexer. Your job is to read page-by-page content and produce a hierarchical Table of Contents (ToC) tree — exactly like the PageIndex framework.

Rules:
- Each node represents a logical section of the document
- node_id: zero-padded 4-digit string, e.g. "0001", "0002"
- title: the section heading as it appears in text
- summary: 1-2 sentence description of what this section covers
- page_index: the page number (0-based) where this section starts
- nodes: list of child nodes (sub-sections)
- Produce 5–20 top-level nodes with appropriate sub-nodes
- Return ONLY valid JSON, no markdown fences"""

def build_toc_tree(pages: list[str]) -> tuple[list[dict], dict]:
    """
    Pass page content to Claude → get back a ToC tree as a list of nodes.
    Returns (tree, stats) where stats = {tokens, latency_sec}.
    """
    page_text_parts = []
    for i, page in enumerate(pages[:40]):
        snippet = page[:600]
        page_text_parts.append(f"<page_{i}>\n{snippet}\n</page_{i}>")

    combined = "\n\n".join(page_text_parts)

    prompt = f"""Build a hierarchical Table of Contents tree for this {len(pages)}-page document.

{combined}

Return a JSON array of nodes. Each node:
{{
  "node_id": "0001",
  "title": "Section Title",
  "summary": "Brief description of what this section covers.",
  "page_index": 0,
  "nodes": [ ...child nodes... ]
}}

Return ONLY the JSON array, nothing else."""

    t0 = time.time()
    raw, tok_in, tok_out = _call(TOC_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=3000)
    latency = round(time.time() - t0, 2)
    tokens = tok_in + tok_out
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        tree = json.loads(raw)
        tree = tree if isinstance(tree, list) else tree.get("nodes", [])
    except json.JSONDecodeError:
        tree = [{
            "node_id": "0001",
            "title": "Full Document",
            "summary": "Complete document content.",
            "page_index": 0,
            "nodes": []
        }]

    return tree, {"tokens": tokens, "latency_sec": latency}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: tree pretty-print + node lookup
# ─────────────────────────────────────────────────────────────────────────────

def flatten_nodes(nodes: list[dict], depth: int = 0) -> list[dict]:
    """Return all nodes in the tree as a flat list with depth info."""
    flat = []
    for node in nodes:
        flat.append({**node, "_depth": depth})
        flat.extend(flatten_nodes(node.get("nodes", []), depth + 1))
    return flat


def tree_to_display_string(nodes: list[dict], indent: int = 0) -> str:
    """Render tree as a readable indented string for display."""
    lines = []
    for node in nodes:
        prefix = "  " * indent
        marker = "├─" if indent > 0 else "▸"
        lines.append(f"{prefix}{marker} [{node['node_id']}] p.{node.get('page_index',0)+1}  {node['title']}")
        lines.append(f"{'  '*(indent+1)}  {node.get('summary','')}")
        if node.get("nodes"):
            lines.append(tree_to_display_string(node["nodes"], indent + 1))
    return "\n".join(lines)


def get_node_by_id(nodes: list[dict], node_id: str) -> dict | None:
    """Find a node by node_id recursively."""
    for node in nodes:
        if node["node_id"] == node_id:
            return node
        found = get_node_by_id(node.get("nodes", []), node_id)
        if found:
            return found
    return None


def get_page_range(node: dict, total_pages: int) -> tuple[int, int]:
    """Get start and end page for a node."""
    start = node.get("page_index", 0)
    # Try to find end from sub-nodes or use start+3 heuristic
    sub_nodes = node.get("nodes", [])
    if sub_nodes:
        last_sub = flatten_nodes(sub_nodes)[-1]
        end = last_sub.get("page_index", start + 2)
    else:
        end = min(start + 3, total_pages - 1)
    return start, end


def retrieve_pages_for_node(node: dict, pages: list[str]) -> str:
    """Get the page text content for a given node."""
    start, end = get_page_range(node, len(pages))
    selected = pages[start: end + 1]
    parts = []
    for i, text in enumerate(selected):
        page_num = start + i + 1
        parts.append(f"--- Page {page_num} ---\n{text}")
    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 + 4: Reasoning retrieval → Answer
# ─────────────────────────────────────────────────────────────────────────────

RETRIEVAL_SYSTEM = """You are a PageIndex Reasoning Retriever.

Given a document's Table of Contents tree and a user query, your job is to:
1. Reason about which node(s) in the tree are most likely to contain the answer
2. Return ONLY a JSON object with your reasoning and selected node IDs

Return format (JSON only, no markdown):
{
  "reasoning": "Your step-by-step reasoning about which sections to look at",
  "primary_node_id": "0005",
  "secondary_node_ids": ["0006", "0007"]
}

secondary_node_ids can be empty []. Only include nodes that are truly relevant."""


ANSWER_SYSTEM = """You are a document QA assistant using PageIndex reasoning-based retrieval.

You have been given:
1. A user query
2. Specific pages from the document that were selected by reasoning over the Table of Contents

Answer the query based ONLY on the provided page content. Be specific and cite page numbers.
If the content doesn't contain enough information, say so clearly."""


def retrieve_and_answer(
    query: str,
    toc_tree: list[dict],
    pages: list[str],
    chat_history: list[dict] | None = None,
    trace=None,   # optional QueryTrace from observability.py
) -> dict:
    """
    Full PageIndex RAG pipeline for one query.
    Returns dict with: answer, reasoning, nodes_read, page_content_preview, tokens
    """
    all_nodes = flatten_nodes(toc_tree)
    nodes_summary = "\n".join(
        f"[{n['node_id']}] p.{n.get('page_index',0)+1}: {n['title']} — {n.get('summary','')}"
        for n in all_nodes
    )

    history_str = ""
    if chat_history:
        recent = chat_history[-4:]
        history_str = "\n".join(
            f"{'User' if m['role']=='user' else 'Assistant'}: {m['content'][:200]}"
            for m in recent
        )

    # ── Step 3: Reasoning retrieval ───────────────────────────────────────────
    retrieval_prompt = f"""Document Table of Contents:
{nodes_summary}

{f"Previous conversation:{chr(10)}{history_str}{chr(10)}" if history_str else ""}
Query: {query}

Which node(s) contain the answer?"""

    t0 = time.time()
    raw, r_in, r_out = _call(RETRIEVAL_SYSTEM, [{"role": "user", "content": retrieval_prompt}], max_tokens=600)
    r_latency = round(time.time() - t0, 2)
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        retrieval_result = json.loads(raw)
    except Exception:
        retrieval_result = {
            "reasoning": "Could not parse retrieval response.",
            "primary_node_id": all_nodes[0]["node_id"] if all_nodes else "0001",
            "secondary_node_ids": []
        }

    primary_id = retrieval_result.get("primary_node_id", "")
    secondary_ids = retrieval_result.get("secondary_node_ids", [])
    reasoning = retrieval_result.get("reasoning", "")

    if trace:
        trace.log_toc_reasoning(
            nodes_count=len(all_nodes),
            reasoning=reasoning,
            primary_id=primary_id,
            secondary_ids=secondary_ids,
            tok_in=r_in, tok_out=r_out,
            latency=r_latency,
        )

    # ── Step 3b: Fetch pages for selected nodes ───────────────────────────────
    nodes_read = []
    page_contents = []
    pages_fetched = 0

    for nid in ([primary_id] + secondary_ids)[:3]:
        node = get_node_by_id(toc_tree, nid)
        if node:
            content = retrieve_pages_for_node(node, pages)
            start, end = get_page_range(node, len(pages))
            pages_fetched += end - start + 1
            nodes_read.append({
                "node_id": nid,
                "title": node.get("title", ""),
                "page_index": node.get("page_index", 0),
                "is_primary": nid == primary_id
            })
            page_contents.append(f"=== Node [{nid}]: {node.get('title','')} ===\n{content}")

    combined_content = "\n\n".join(page_contents) if page_contents else "No content retrieved."

    if trace:
        trace.log_page_retrieval(
            nodes_read=nodes_read,
            pages_fetched=pages_fetched,
            chars=len(combined_content),
        )

    # ── Step 4: Generate answer ───────────────────────────────────────────────
    answer_messages = []
    if chat_history:
        for msg in chat_history[-4:]:
            answer_messages.append({"role": msg["role"], "content": msg["content"]})
    answer_messages.append({
        "role": "user",
        "content": f"Retrieved document content:\n{combined_content[:4000]}\n\nQuery: {query}"
    })

    t0 = time.time()
    answer, a_in, a_out = _call(ANSWER_SYSTEM, answer_messages, max_tokens=1000)
    a_latency = round(time.time() - t0, 2)

    if trace:
        trace.log_answer_gen(
            answer=answer,
            tok_in=a_in, tok_out=a_out,
            latency=a_latency,
        )

    return {
        "answer": answer,
        "reasoning": reasoning,
        "nodes_read": nodes_read,
        "page_content_preview": combined_content[:500],
        "tokens": r_in + r_out + a_in + a_out,
    }