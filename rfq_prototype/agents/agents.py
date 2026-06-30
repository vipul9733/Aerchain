"""
Agents: thin orchestration over the Prompt Pack.

Every agent call optionally records a trace (input -> prompt -> raw output ->
final structured output) so the Prompt Trace deliverable is produced
automatically by real runs rather than hand-written.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from prompts import prompt_pack as pp
from utils.llm_client import complete, complete_json


@dataclass
class Trace:
    """One captured agent run, for the Prompt Trace screen / deliverable."""
    agent: str
    system_prompt: str
    user_prompt: str
    raw_output: str
    final_output: Any
    extras: dict = field(default_factory=dict)


# ---- 1. RFQ generation ----------------------------------------------------
def generate_rfq(traces: list[Trace] | None = None) -> dict:
    user = pp.RFQ_GENERATION_USER
    result = complete_json(pp.RFQ_GENERATION_SYSTEM, user, max_tokens=4096, temperature=0.5)
    if traces is not None:
        traces.append(Trace(
            agent="RFQ Generation Agent (v1.0)",
            system_prompt=pp.RFQ_GENERATION_SYSTEM,
            user_prompt=user,
            raw_output=json.dumps(result, indent=2),
            final_output=result,
        ))
    return result


# ---- 2. Vendor response generation ---------------------------------------
def generate_vendor_response(rfq: dict, preset: dict, traces: list[Trace] | None = None) -> dict:
    user = pp.VENDOR_GENERATION_USER.format(
        rfq_json=json.dumps(rfq, indent=2),
        persona=preset["persona"],
        defects=preset["defects"],
    )
    text = complete(pp.VENDOR_GENERATION_SYSTEM, user, max_tokens=4096, temperature=0.8)
    record = {"vendor_name": preset["name"], "text": text.strip()}
    if traces is not None:
        traces.append(Trace(
            agent=f"Vendor Generation Agent (v1.1) — {preset['name']}",
            system_prompt=pp.VENDOR_GENERATION_SYSTEM,
            user_prompt=user,
            raw_output=text,
            final_output=record,
        ))
    return record


# ---- 3. UI/UX generation --------------------------------------------------
def generate_uiux(traces: list[Trace] | None = None) -> dict:
    user = pp.UIUX_GENERATION_USER
    result = complete_json(pp.UIUX_GENERATION_SYSTEM, user, max_tokens=3072, temperature=0.5)
    if traces is not None:
        traces.append(Trace(
            agent="UI/UX Generation Agent (v1.0)",
            system_prompt=pp.UIUX_GENERATION_SYSTEM,
            user_prompt=user,
            raw_output=json.dumps(result, indent=2),
            final_output=result,
        ))
    return result


# ---- 4. Extraction --------------------------------------------------------
def extract_vendor(vendor_name: str, vendor_text: str, line_item_names: list[str],
                   traces: list[Trace] | None = None) -> dict:
    user = pp.EXTRACTION_USER.format(
        vendor_name=vendor_name,
        vendor_text=vendor_text,
        line_item_names="\n".join(f"- {n}" for n in line_item_names),
    )
    result = complete_json(pp.EXTRACTION_SYSTEM, user, max_tokens=8192, temperature=0.1)
    result.setdefault("vendor_name", vendor_name)
    if traces is not None:
        traces.append(Trace(
            agent=f"Extraction Agent (v1.2) — {vendor_name}",
            system_prompt=pp.EXTRACTION_SYSTEM,
            user_prompt=user,
            raw_output=json.dumps(result, indent=2),
            final_output=result,
            extras={"input_chars": len(vendor_text)},
        ))
    return result


# ---- 5. Comparison --------------------------------------------------------
def compare_vendors(extractions: list[dict], traces: list[Trace] | None = None) -> dict:
    user = pp.COMPARISON_USER.format(extractions_json=json.dumps(extractions, indent=2))
    result = complete_json(pp.COMPARISON_SYSTEM, user, max_tokens=8192, temperature=0.2)
    if traces is not None:
        traces.append(Trace(
            agent="Comparison Agent (v1.1)",
            system_prompt=pp.COMPARISON_SYSTEM,
            user_prompt=user,
            raw_output=json.dumps(result, indent=2),
            final_output=result,
            extras={"vendor_count": len(extractions)},
        ))
    return result


# ---- 6. Clarification -----------------------------------------------------
def draft_clarification(vendor_name: str, flags: list[dict],
                        traces: list[Trace] | None = None) -> str:
    user = pp.CLARIFICATION_USER.format(
        vendor_name=vendor_name,
        flags_json=json.dumps(flags, indent=2),
    )
    text = complete(pp.CLARIFICATION_SYSTEM, user, max_tokens=1024, temperature=0.4)
    if traces is not None:
        traces.append(Trace(
            agent=f"Clarification Agent (v1.0) — {vendor_name}",
            system_prompt=pp.CLARIFICATION_SYSTEM,
            user_prompt=user,
            raw_output=text,
            final_output=text.strip(),
        ))
    return text.strip()