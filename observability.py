# """
# Langfuse Observability for PageIndex Doc QA
# ────────────────────────────────────────────
# Traces 4 distinct steps per query:
#   1. toc_reasoning   — LLM picks node_ids from the ToC
#   2. page_retrieval  — physical pages fetched for those nodes
#   3. answer_gen      — LLM produces the final answer

# Plus a one-off trace when the document is indexed:
#   0. document_index  — PDF pages → ToC tree build

# Sign up free at https://cloud.langfuse.com → copy Public + Secret keys.
# """

import os
import time

def is_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))

def _get():
    if not is_enabled():
        return None
    try:
        from langfuse import get_client
        return get_client()
    except Exception:
        return None


def trace_index(session_id, doc_name, total_pages, total_nodes, tokens, latency_sec):
    lf = _get()
    if not lf:
        return
    try:
        with lf.start_as_current_observation(as_type="span", name="pageindex_index") as span:
            span.update(
                input={"doc": doc_name, "pages": total_pages},
                output={"nodes": total_nodes},
                metadata={"tokens": str(tokens), "latency_sec": str(latency_sec)},
            )
        lf.flush()
    except Exception as e:
        print(f"[Langfuse] trace_index error: {e}")


class QueryTrace:
    def __init__(self, session_id: str, doc_name: str, query: str):
        self._lf = _get()
        self._t0 = time.time()
        self._data = {
            "toc_reasoning": None,
            "page_retrieval": None,
            "answer_gen": None,
        }
        self._query = query
        self._doc = doc_name

    def log_toc_reasoning(self, *, nodes_count, reasoning, primary_id,
                          secondary_ids, tok_in, tok_out, latency):
        self._data["toc_reasoning"] = {
            "nodes_count": nodes_count, "reasoning": reasoning[:400],
            "primary_id": primary_id, "secondary_ids": secondary_ids,
            "tok_in": tok_in, "tok_out": tok_out, "latency": latency,
        }

    def log_page_retrieval(self, *, nodes_read, pages_fetched, chars):
        self._data["page_retrieval"] = {
            "nodes": [n["node_id"] for n in nodes_read],
            "pages_fetched": pages_fetched, "chars": chars,
        }

    def log_answer_gen(self, *, answer, tok_in, tok_out, latency):
        self._data["answer_gen"] = {
            "answer": answer[:800],
            "tok_in": tok_in, "tok_out": tok_out, "latency": latency,
        }

    def finish(self, answer: str, total_tokens: int, nodes_read: int):
        lf = self._lf
        if not lf:
            return
        try:
            with lf.start_as_current_observation(as_type="span", name="pageindex_query") as root:
                root.update(
                    input={"query": self._query, "doc": self._doc},
                    output={"answer": answer[:400]},
                    metadata={
                        "total_tokens": str(total_tokens),
                        "nodes_read": str(nodes_read),
                        "total_latency_sec": str(round(time.time() - self._t0, 2)),
                    },
                )
                # toc_reasoning
                if self._data["toc_reasoning"]:
                    d = self._data["toc_reasoning"]
                    with lf.start_as_current_observation(as_type="generation", name="toc_reasoning") as g:
                        g.update(
                            input={"toc_nodes": d["nodes_count"]},
                            output={"primary": d["primary_id"], "reasoning": d["reasoning"]},
                            metadata={"latency_sec": str(d["latency"])},
                        )
                # page_retrieval
                if self._data["page_retrieval"]:
                    d = self._data["page_retrieval"]
                    with lf.start_as_current_observation(as_type="span", name="page_retrieval") as s:
                        s.update(
                            input={"nodes": d["nodes"]},
                            output={"pages_fetched": d["pages_fetched"]},
                        )
                # answer_gen
                if self._data["answer_gen"]:
                    d = self._data["answer_gen"]
                    with lf.start_as_current_observation(as_type="generation", name="answer_gen") as g:
                        g.update(
                            input="[retrieved pages]",
                            output=d["answer"],
                            metadata={"latency_sec": str(d["latency"])},
                        )
            lf.flush()
        except Exception as e:
            print(f"[Langfuse] finish error: {e}")
