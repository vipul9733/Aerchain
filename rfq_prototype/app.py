from __future__ import annotations

import json
import os

import streamlit as st

from agents import agents
from agents.agents import Trace
from prompts import prompt_pack as pp
from utils import llm_client
from utils.input_parser import parse_uploaded_file

DATA = os.path.join(os.path.dirname(__file__), "data")

st.set_page_config(page_title="RFQ Procurement Intelligence", layout="wide", page_icon="◆")

# ---------------------------------------------------------------------------
# Styling — restrained, document-like. Ink on warm paper, one signal colour
# reserved entirely for risk. The palette is deliberately quiet so the only
# loud thing on screen is a flagged gap.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
:root{
  --ink:#1d2024; --paper:#fbfaf7; --line:#e4e0d8;
  --present:#2f7d52; --missing:#9aa0a6; --unclear:#b8860b; --conflicting:#c0392b; --risk:#c0392b;
}
.stApp{background:var(--paper);}
.block-container{max-width:1180px;}
h1,h2,h3{font-family:Georgia,'Times New Roman',serif;color:var(--ink);letter-spacing:-.01em;}
.eyebrow{font:600 11px/1.4 ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:#8a8578;}
.chip{display:inline-block;padding:1px 9px;border-radius:10px;font:600 11px/1.6 ui-monospace,monospace;
      text-transform:uppercase;letter-spacing:.04em;}
.chip.present{background:#e7f3ec;color:var(--present);}
.chip.missing{background:#eef0f1;color:var(--missing);}
.chip.unclear{background:#fbf2d9;color:var(--unclear);}
.chip.conflicting,.chip.risk{background:#fbe7e4;color:var(--conflicting);}
.evidence{border-left:3px solid var(--line);padding:.2em .8em;margin:.3em 0;color:#55504a;
          font:italic 14px/1.5 Georgia,serif;background:#f5f3ee;}
.card{border:1px solid var(--line);border-radius:8px;padding:1.1em 1.3em;background:#fff;margin-bottom:.8em;}
.banner{border:1px solid var(--line);border-left:5px solid var(--ink);border-radius:6px;
        padding:1em 1.3em;background:#fff;margin-bottom:1em;}
.banner.warn{border-left-color:var(--conflicting);}
.flagrow{padding:.5em .8em;border-bottom:1px solid var(--line);}
small.basis{color:#8a8578;font:400 12px/1.4 ui-monospace,monospace;}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# State + data loading
# ---------------------------------------------------------------------------
def _load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


def init_state():
    ss = st.session_state
    if "loaded" in ss:
        return
    try:
        ss.rfq = _load("rfq.json")
        ss.vendors = _load("vendors.json")
        ss.extractions = _load("extractions.json")
        ss.comparison = _load("comparison.json")
        ss.uiux = _load("uiux_spec.json")
        ss.traces_data = _load("traces.json")
    except FileNotFoundError:
        for k in ("rfq", "vendors", "extractions", "comparison", "uiux"):
            ss[k] = None
        ss.traces_data = []
    ss.live_traces: list[Trace] = []
    ss.loaded = True


def has_key() -> bool:
    return llm_client.has_credentials()


init_state()
ss = st.session_state


# ---------------------------------------------------------------------------
# Sidebar — paste a key to switch from sample data to live AI calls.
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="eyebrow">Connection</div>', unsafe_allow_html=True)
    provider = st.selectbox("Provider", ["anthropic", "openai"], index=0)
    key_in = st.text_input(
        "API key",
        type="password",
        value=ss.get("api_key", ""),
        placeholder="sk-ant-…  (Claude)  or  sk-…  (OpenAI)",
        help="Pasted here it stays in this session only. Leave empty to browse the generated sample data.",
    )
    model_in = st.text_input("Model (optional)", value=ss.get("model_override", ""),
                             placeholder="defaults to a sensible model")

    ss.api_key = key_in
    ss.model_override = model_in
    # Push credentials into the client every run so live calls use them.
    if key_in.strip():
        llm_client.set_runtime_credentials(provider=provider, api_key=key_in, model=model_in or None)
    else:
        llm_client.clear_runtime_credentials()

    if llm_client.has_credentials():
        st.success("Live mode ON — generation, extraction, comparison and email drafting will call the API.")
    else:
        st.info("Sample mode — showing pre-generated data. Paste a key to run the AI live on your own input.")

    st.caption("Tip for reviewers: paste a key, go to ② Vendor Upload, paste a new vendor, and Run extraction "
               "to see the AI process fresh input live (not hardcoded).")


def chip(status: str) -> str:
    s = (status or "missing").lower()
    return f'<span class="chip {s}">{s}</span>'


def render_value(obj: dict):
    """Render a {value,status,evidence} object."""
    if not isinstance(obj, dict):
        st.write(obj)
        return
    st.markdown(f"{chip(obj.get('status'))} &nbsp; {obj.get('value') or '—'}", unsafe_allow_html=True)
    if obj.get("evidence"):
        st.markdown(f'<div class="evidence">“{obj["evidence"]}”</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown('<div class="eyebrow">Procurement Intelligence · Prompt-Driven Prototype</div>', unsafe_allow_html=True)
st.title("RFQ → Vendor Extraction → Comparison")
if not has_key():
    st.caption("Sample mode — browsing generated data. Paste an API key in the sidebar (left) to run the AI live.")

tabs = st.tabs(["① RFQ Overview", "② Vendor Upload", "③ Extraction Review", "④ Vendor Comparison", "⑤ Prompt Trace"])

# ===========================================================================
# SCREEN 1 — RFQ OVERVIEW
# ===========================================================================
with tabs[0]:
    rfq = ss.rfq
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("Regenerate RFQ", disabled=not has_key(), use_container_width=True):
            with st.spinner("Generating RFQ…"):
                ss.rfq = agents.generate_rfq(ss.live_traces)
                st.rerun()
    if not rfq:
        st.info("No RFQ loaded. Generate one to begin.")
    else:
        with c1:
            st.subheader(rfq["title"])
            st.markdown(f'<span class="eyebrow">{rfq["rfq_id"]} · {rfq["issuing_entity"]}</span>', unsafe_allow_html=True)
        gi = rfq["general_information"]
        st.markdown(f'<div class="card"><b>Background.</b> {gi["background"]}<br><br>'
                    f'<b>Objective.</b> {gi["objective"]}<br><br>'
                    f'<b>Due.</b> {gi["response_due_date"]} &nbsp;·&nbsp; <b>Currency.</b> {gi["currency"]} &nbsp;·&nbsp; '
                    f'<b>Contact.</b> {gi["contact"]}</div>', unsafe_allow_html=True)

        st.markdown("#### Line items")
        for li in rfq["line_items"]:
            with st.expander(f'{li["id"]}. {li["name"]}  ·  priced as: {li["requested_unit"]}'):
                st.write(li["scope"])
                st.markdown("**Deliverables:** " + ", ".join(li["deliverables"]))

        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("#### Commercial expectations")
            ce = rfq["commercial_expectations"]
            st.markdown(f'<div class="card">{ce["pricing_format"]}<br><br>'
                        f'<b>Tax.</b> {ce["tax_clarity"]}<br><br>'
                        f'<b>Payment.</b> {ce["payment_terms"]}</div>', unsafe_allow_html=True)
            st.markdown("#### Evaluation weights")
            for ev in rfq["evaluation_criteria"]:
                st.markdown(f'- {ev["criterion"]} — **{ev["weight_percent"]}%**')
        with cc2:
            st.markdown("#### Vendor questionnaire")
            for q in rfq["vendor_questionnaire"]:
                st.markdown(f"- {q}")
            st.markdown("#### Compliance requirements")
            for cr in rfq["compliance_requirements"]:
                st.markdown(f'- **{cr["area"]}.** {cr["requirement"]}')

        st.markdown("#### Timeline")
        st.table([{"Milestone": t["milestone"], "Date": t["date"]} for t in rfq["timelines"]])

# ===========================================================================
# SCREEN 2 — VENDOR UPLOAD / INPUT
# ===========================================================================
with tabs[1]:
    st.subheader("Add vendor responses")
    st.caption("Paste text, upload files (txt / md / json / pdf / docx), or load the generated sample set. "
               "The AI reads exactly what you provide — nothing is hardcoded.")

    colu1, colu2 = st.columns(2)
    with colu1:
        uploaded = st.file_uploader("Upload vendor files", accept_multiple_files=True,
                                    type=["txt", "md", "json", "pdf", "docx"])
        if uploaded:
            new = []
            for f in uploaded:
                text = parse_uploaded_file(f.name, f.read())
                new.append({"vendor_name": os.path.splitext(f.name)[0], "text": text})
            ss.vendors = new
            st.success(f"Loaded {len(new)} vendor file(s).")
    with colu2:
        pasted_name = st.text_input("Vendor name (for paste)")
        pasted_text = st.text_area("Paste a vendor response", height=160)
        cpa, cpb = st.columns(2)
        with cpa:
            if st.button("Add pasted vendor", use_container_width=True) and pasted_text.strip():
                ss.vendors = (ss.vendors or []) + [{"vendor_name": pasted_name or "Pasted Vendor", "text": pasted_text}]
                st.success("Added.")
        with cpb:
            if st.button("Load sample vendors", use_container_width=True):
                ss.vendors = _load("vendors.json")
                st.success("Sample vendors loaded.")

    st.divider()
    if ss.vendors:
        st.markdown(f"**{len(ss.vendors)} vendor response(s) ready:**")
        for v in ss.vendors:
            with st.expander(v["vendor_name"]):
                st.text(v["text"][:1500] + ("…" if len(v["text"]) > 1500 else ""))
        run_disabled = not has_key()
        if st.button("▶ Run extraction on all vendors", type="primary", disabled=run_disabled):
            line_items = [li["name"] for li in (ss.rfq or {}).get("line_items", [])]
            results = []
            prog = st.progress(0.0)
            for i, v in enumerate(ss.vendors):
                with st.spinner(f"Extracting {v['vendor_name']}…"):
                    results.append(agents.extract_vendor(v["vendor_name"], v["text"], line_items, ss.live_traces))
                prog.progress((i + 1) / len(ss.vendors))
            ss.extractions = results
            st.success("Extraction complete — see the Extraction Review tab.")
        if run_disabled:
            st.info("No API key set, so live extraction is disabled. The Extraction Review tab shows pre-generated results.")
    else:
        st.info("No vendor responses yet. Paste, upload, or load the sample set.")

# ===========================================================================
# SCREEN 3 — EXTRACTION REVIEW
# ===========================================================================
with tabs[2]:
    st.subheader("What each vendor actually said")
    st.caption("Every field carries a status and, where present, a verbatim evidence snippet. "
               "Nothing shows as ‘present’ without evidence.")
    exs = ss.extractions
    if not exs:
        st.info("Run extraction (Vendor Upload tab) to see results.")
    else:
        names = [e["vendor_name"] for e in exs]
        pick = st.radio("Vendor", names, horizontal=True)
        e = next(x for x in exs if x["vendor_name"] == pick)

        st.markdown(f'<div class="banner">{e["overall_summary"]}</div>', unsafe_allow_html=True)

        # Flags first — the buyer should see risk before detail.
        flags = e.get("flags", [])
        if flags:
            st.markdown(f"#### ⚑ Flags ({len(flags)})")
            for fl in flags:
                ev = f'<div class="evidence">“{fl["evidence"]}”</div>' if fl.get("evidence") else ""
                st.markdown(f'<div class="flagrow">{chip(fl["type"])} &nbsp; <b>{fl["field"]}</b> — {fl["detail"]}{ev}</div>',
                            unsafe_allow_html=True)

        st.markdown("#### Line-item coverage")
        cov_map = {"yes": "present", "partial": "unclear", "no": "missing", "unclear": "unclear"}
        for li in e.get("line_item_coverage", []):
            with st.expander(f'{li["line_item"]} — {li["covered"].upper()}'):
                st.markdown(chip(cov_map.get(li["covered"], "missing")), unsafe_allow_html=True)
                st.markdown("**Scope**"); render_value(li.get("scope_notes", {}))
                st.markdown("**Price**"); render_value(li.get("price", {}))

        cce1, cce2 = st.columns(2)
        with cce1:
            st.markdown("#### Commercials")
            for label, key in [("Total / bundled", "total_or_bundled_price"), ("Currency", "currency"),
                               ("Tax", "tax_treatment"), ("Payment terms", "payment_terms"),
                               ("Pricing model", "pricing_model")]:
                st.markdown(f"**{label}**"); render_value(e["commercials"].get(key, {}))
        with cce2:
            st.markdown("#### Timeline"); render_value(e.get("timeline", {}))
            st.markdown("#### Compliance")
            st.markdown("**Kids advertising / claims**"); render_value(e["compliance"].get("kids_advertising_claims", {}))
            st.markdown("**General**"); render_value(e["compliance"].get("general_compliance", {}))
            if e.get("assumptions"):
                st.markdown("#### Assumptions")
                for a in e["assumptions"]:
                    st.markdown(f"- {a}")
            if e.get("exclusions"):
                st.markdown("#### Exclusions")
                for x in e["exclusions"]:
                    st.markdown(f"- {x}")

# ===========================================================================
# SCREEN 4 — VENDOR COMPARISON
# ===========================================================================
with tabs[3]:
    st.subheader("How the vendors compare")
    cmp = ss.comparison
    cco = st.columns([3, 1])[1]
    with cco:
        if st.button("Re-run comparison", disabled=not (has_key() and ss.extractions), use_container_width=True):
            with st.spinner("Comparing…"):
                ss.comparison = agents.compare_vendors(ss.extractions, ss.live_traces)
                st.rerun()
    if not cmp:
        st.info("Run extraction and comparison to see results.")
    else:
        # Comparability banner — the first thing the buyer reads.
        not_ready = [c for c in cmp["comparability_status"] if c["status"] != "comparable"]
        warn = "warn" if not_ready else ""
        lines = "<br>".join(f'{chip("conflicting" if c["status"]!="comparable" else "present")} '
                            f'<b>{c["vendor"]}</b> — {c["reason"]}' for c in cmp["comparability_status"])
        st.markdown(f'<div class="banner {warn}"><b>Comparability check.</b><br>{lines}</div>', unsafe_allow_html=True)

        st.markdown("#### Buyer attention — read first")
        for b in cmp["buyer_attention"]:
            st.markdown(f"- {b}")

        st.markdown("#### Dimension matrix")
        vendors = [c["vendor"] for c in cmp["comparability_status"]]
        for dim in cmp["dimension_matrix"]:
            header = dim["dimension"]
            if not dim.get("comparable", True):
                header += "  ·  ⚠ not comparable"
            with st.expander(header, expanded=not dim.get("comparable", True)):
                if not dim.get("comparable", True) and dim.get("note_if_not_comparable"):
                    st.markdown(f'{chip("conflicting")} {dim["note_if_not_comparable"]}', unsafe_allow_html=True)
                for pv in dim["per_vendor"]:
                    st.markdown(f'**{pv["vendor"]}** &nbsp; {chip(pv["confidence"] if pv["confidence"] in ("high","medium","low") else "unclear")}'
                                .replace('chip high','chip present').replace('chip low','chip missing').replace('chip medium','chip unclear'),
                                unsafe_allow_html=True)
                    st.markdown(pv["assessment"])
                    st.markdown(f'<small class="basis">basis: {pv["basis"]}</small>', unsafe_allow_html=True)
                    st.write("")

        cd1, cd2 = st.columns(2)
        with cd1:
            st.markdown("#### Key differences")
            for k in cmp["key_differences"]:
                st.markdown(f"- {k}")
        with cd2:
            st.markdown("#### Missing info blocking comparison")
            for m in cmp["missing_info_blocking_comparison"]:
                st.markdown(f'- **{m["vendor"]}** — {m["missing"]} _{m["why_it_matters"]}_')

        st.markdown("#### Clarification questions to send")
        for q in cmp["clarification_questions"]:
            st.markdown(f'- **{q["vendor"]}** — {q["question"]}')
        if has_key():
            st.divider()
            vsel = st.selectbox("Draft a clarification email for", vendors)
            if st.button("✎ Draft clarification email"):
                ex = next((x for x in (ss.extractions or []) if x["vendor_name"] == vsel), None)
                flags = ex.get("flags", []) if ex else []
                with st.spinner("Drafting…"):
                    email = agents.draft_clarification(vsel, flags, ss.live_traces)
                st.text_area("Draft email", email, height=300)

# ===========================================================================
# SCREEN 5 — PROMPT TRACE
# ===========================================================================
with tabs[4]:
    st.subheader("How the AI reached this")
    st.caption("Input → prompt → raw model output → final structured output, for any agent run.")

    live = ss.live_traces
    if live:
        st.markdown(f"**{len(live)} live trace(s) captured this session:**")
        labels = [t.agent for t in live]
        idx = st.selectbox("Live trace", range(len(labels)), format_func=lambda i: labels[i])
        t = live[idx]
        with st.expander("System prompt", expanded=False):
            st.code(t.system_prompt)
        with st.expander("User prompt (input + instructions)", expanded=True):
            st.code(t.user_prompt[:6000])
        with st.expander("Raw model output", expanded=False):
            st.code(t.raw_output[:6000])
        with st.expander("Final structured output", expanded=False):
            st.json(t.final_output if isinstance(t.final_output, (dict, list)) else {"text": t.final_output})
        st.divider()

    st.markdown("#### Saved reference traces")
    saved = ss.traces_data or []
    for tr in saved:
        with st.expander(tr["agent"]):
            st.markdown("**System prompt**"); st.code(tr["system_prompt"][:2500])
            st.markdown("**User prompt**"); st.code(tr["user_prompt"][:3500])
            st.markdown("**Raw output**"); st.code(tr["raw_output"][:3000])
            if tr.get("trace_commentary"):
                st.markdown(f'<div class="banner">{tr["trace_commentary"]}</div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("#### Prompt Pack")
    st.caption("The actual prompts powering every agent.")
    pack = {
        "RFQ Generation": (pp.RFQ_GENERATION_SYSTEM, pp.RFQ_GENERATION_USER),
        "Vendor Generation": (pp.VENDOR_GENERATION_SYSTEM, pp.VENDOR_GENERATION_USER),
        "UI/UX Generation": (pp.UIUX_GENERATION_SYSTEM, pp.UIUX_GENERATION_USER),
        "Extraction": (pp.EXTRACTION_SYSTEM, pp.EXTRACTION_USER),
        "Comparison": (pp.COMPARISON_SYSTEM, pp.COMPARISON_USER),
        "Clarification": (pp.CLARIFICATION_SYSTEM, pp.CLARIFICATION_USER),
    }
    choice = st.selectbox("Prompt", list(pack.keys()))
    sysp, usrp = pack[choice]
    st.markdown("**System**"); st.code(sysp)
    st.markdown("**User template**"); st.code(usrp)
