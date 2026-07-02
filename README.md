# RFQ Procurement Intelligence — Prompt-Driven Prototype

A working AI prototype for a real procurement workflow: it **generates** a realistic RFQ and messy vendor responses, **extracts** structured procurement data with evidence, **flags** what's missing / unclear / conflicting, and **compares** vendors for a buyer — without hallucinating.

Flow: **RFQ Generation → Vendor Response Input → Extraction Agent → Comparison Agent → Buyer-Facing UI**, with a Prompt Trace view.

---

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. (Optional) set a key to enable LIVE generation/extraction/comparison.
#    Without a key, the app runs fully on shipped sample data.
export ANTHROPIC_API_KEY=sk-...            # default provider
#   or:
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# 3. Run
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

---

## What runs with vs. without an API key

| Capability | No key | With key |
|---|---|---|
| Browse RFQ, extractions, comparison, traces (sample data) | ✅ | ✅ |
| Paste / upload your own vendor responses | ✅ | ✅ |
| **Regenerate RFQ** live | — | ✅ |
| **Run extraction** on your own vendor inputs | — | ✅ |
| **Re-run comparison** live | — | ✅ |
| **Draft clarification emails** | — | ✅ |

The sample data in `data/` was itself produced by the prompts (see the Prompt Trace tab), not hand-written.

---

## Regenerate the entire sample dataset from prompts

```bash
export ANTHROPIC_API_KEY=sk-...
python generate_sample_data.py
```

This re-runs every agent end to end and rewrites `data/*.json`, including full prompt traces.

---

## Project layout

```
app.py                     Streamlit app — the 5 buyer-facing screens
generate_sample_data.py    Re-creates data/ by running the prompts
prompts/prompt_pack.py     ★ The Prompt Pack — all agent prompts + rationale
agents/agents.py           Thin orchestration; captures prompt traces
utils/llm_client.py        Provider-agnostic LLM client (Anthropic / OpenAI) + JSON repair
utils/input_parser.py      txt / md / json / pdf / docx vendor input parsing
data/                      Generated RFQ, vendors, extractions, comparison, traces, UI/UX spec
WRITEUP.md                 1–2 page product & prompt-architecture write-up
```

## Configuration

| Env var | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | — | required only for live runs |
| `LLM_MODEL` | provider default | override the model |

## Assumptions
- The RFQ scenario is a fictional Indian kids' cereal launch (so kids-advertising/ASCI compliance is a live, gradeable dimension).
- Full production OCR is out of scope; PDF/DOCX parsing is best-effort, and pasting text always works.
- The three sample vendors are deliberately uneven (lump-sum/conflicting, precise-but-incomplete, all-coverage-but-vague) to stress the extraction and comparison agents.
