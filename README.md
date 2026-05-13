# 📑 PageIndex Document Q&A

> **Vectorless, embedding-free RAG** — answers questions about PDFs by reasoning over a hierarchical Table of Contents tree.

---

## How It Works

Traditional RAG splits documents into chunks and searches with embeddings. PageIndex takes a different approach:

```
PDF → Pages List → LLM builds ToC Tree → Query → LLM reasons over ToC → Fetch matching pages → Answer
```

1. **PDF → Pages** — extracts text from each page
2. **Build ToC Tree** — LLM reads page content and builds a hierarchical Table of Contents (node_id, title, summary, page range)
3. **Reasoning Retrieval** — for each query, LLM reasons over the ToC to pick the most relevant node(s)
4. **Page Fetch** — physical pages for selected nodes are retrieved
5. **Answer Generation** — LLM generates an answer from the retrieved page content

No vectors. No embeddings. No approximate search. Pure structure + reasoning.

---

## Project Structure

```
pageindex/
├── app.py              # Streamlit UI
├── pageindex.py        # Core RAG pipeline (PDF → ToC → Retrieve → Answer)
├── observability.py    # Langfuse tracing (v4 SDK)
├── requirements.txt    # Python dependencies
└── .env                # API keys (never commit this)
```

---

## Quickstart

### 1. Clone & set up environment

```bash
git clone https://github.com/mm-972927/pageindex.git
cd pageindex
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API keys

Create a `.env` file in the project root:

```env
# LLM — Groq (free, fastest)
GROQ_API_KEY=gsk_your_key_here

# Observability — Langfuse (optional but recommended)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 4. Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.
---


## Getting API Keys

| Service | Purpose | Link | Cost |
|---------|---------|------|------|
| Groq | LLM inference | [console.groq.com](https://console.groq.com) | Free (14,400 req/day) |
| Langfuse | Observability & tracing | [cloud.langfuse.com](https://cloud.langfuse.com) | Free tier available |

---

## LLM Configuration

The app uses **Groq** with `llama-3.3-70b-versatile` by default. To change the model, edit `pageindex.py`:

```python
MODEL = "llama-3.3-70b-versatile"   # default — high quality
MODEL = "llama-3.1-8b-instant"      # higher rate limits, faster
MODEL = "mixtral-8x7b-32768"        # longer context window
```

### Switching LLM Providers

<details>
<summary>Anthropic Claude</summary>

```python
import anthropic
anth = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"

def _call(system, messages, max_tokens=1000):
    resp = anth.messages.create(
        model=MODEL, max_tokens=max_tokens,
        system=system, messages=messages,
    )
    return resp.content[0].text.strip(), resp.usage.input_tokens, resp.usage.output_tokens
```
</details>

<details>
<summary>OpenAI</summary>

```python
# Just change the base_url and key in pageindex.py
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"
```
</details>

<details>
<summary>Ollama (fully local)</summary>

```python
client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
MODEL = "llama3.2"
```
</details>

---

## Observability with Langfuse

When Langfuse keys are configured, every query is traced with 3 nested spans:

```
pageindex_query
├── toc_reasoning    — which nodes the LLM selected and why
├── page_retrieval   — pages fetched, character count
└── answer_gen       — final answer, token usage, latency
```

Document indexing is also traced separately as `pageindex_index`.

View traces at [cloud.langfuse.com](https://cloud.langfuse.com) → **Traces** in the left sidebar.

Langfuse is **optional** — the app works fine without it.

---

## Requirements

```
streamlit>=1.32.0
openai>=1.30.0
pypdf>=4.0.0
langfuse>=4.0.0
python-dotenv>=1.0.1
groq>=0.9.0
```

---

## Limitations

- Processes up to **40 pages** for ToC building (configurable in `pageindex.py`)
- Best suited for **structured documents** — reports, papers, manuals, books
- Very short or unstructured PDFs (e.g. scanned images) may produce shallow ToC trees
- Free Groq tier: 14,400 requests/day, 30 requests/minute

---

## License

MIT
