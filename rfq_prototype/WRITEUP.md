# Write-Up — RFQ Procurement Intelligence

## Problem solved
Vendors respond to procurement RFQs in messy, inconsistent ways: bundled pricing, mixed currencies, missing tax terms, vague timelines, unsupported claims, and silence on compliance. Buyers must figure out what each vendor actually said, what's missing, where the risks are, and how vendors differ — fast, and without being misled. This prototype is a prompt-driven AI workflow that does exactly that, end to end.

## Prompt architecture (the core)
Six prompt-driven agents, deliberately split by responsibility:

1. **RFQ Generation** — produces one realistic, fully-structured RFQ for a kids'-cereal launch covering all eight mandated line items, with a demanding questionnaire and compliance section so vendor responses can plausibly fail it.
2. **Vendor Generation** — generates messy proposals driven by an explicit *defect list* per vendor persona. Driving messiness with named defects (not "make it messy") gives controllable, testable complexity: I know exactly which conflicts and gaps the extractor should later catch.
3. **UI/UX Generation** — produces a concrete buyer-facing design spec (screens, copy, how risk is surfaced).
4. **Extraction Agent** — reads one raw proposal and returns structured data where *every field carries a status and verbatim evidence*. Missing/unclear/conflicting are first-class outputs.
5. **Comparison Agent** — reasons **only over the extraction JSON**, never the raw proposals.
6. **Clarification Agent** — turns flags into ready-to-send vendor emails.

**The central design decision is separation of duties.** The extractor only extracts and flags — it never scores or ranks. The comparator only consumes structured extraction output — it literally never sees raw vendor text, so it cannot invent facts into the comparison. This single split is what makes the system's outputs auditable and hard to hallucinate.

## Hallucination control
Three mechanisms, enforced in the prompts:
- **Evidence or absence.** A field may only be marked `present` if it carries a verbatim snippet copied from the source. No evidence ⇒ it must be `missing`/`unclear`. "I don't know" is rewarded, not penalised.
- **Preserve messiness.** The extractor records values as stated ("₹2.4 Cr", "approx one quarter") and never normalises currencies or resolves ambiguity itself — it flags the conflict instead.
- **Grounded comparison.** Because the comparator only sees extracted JSON, every comparison statement traces back to an evidenced extraction field, and dimensions that can't be fairly compared are explicitly marked "not comparable" rather than force-ranked.

## Extraction approach
Per-vendor structured JSON: line-item coverage, commercials, timeline, compliance, assumptions, exclusions, and a dedicated **flags** array (type / field / detail / evidence). The UI surfaces flags *before* detail, because a buyer needs to see risk before reading numbers.

## Comparison approach
A dimension matrix (scope, pricing clarity, commercial completeness, timeline, compliance, risk) with per-vendor assessment, confidence, and the extracted basis for each cell. A comparability banner up top classifies each vendor "comparable now" vs "not yet comparable." The agent never names a winner — it surfaces differences and the specific clarifications needed to close gaps.

## Product thinking / UI decisions
- **What the buyer sees first:** a comparability check and the biggest cross-vendor risk — *before* any price, so nobody anchors on a headline number that isn't like-for-like.
- **Risk is loud, everything else is quiet:** the palette reserves its only strong colour for flags; status chips (present/missing/unclear/conflicting) appear on every field.
- **No false precision:** the comparison refuses to rank on price when no two vendors quote in the same currency/basis — it says so explicitly.
- **Action, not just analysis:** every gap produces a concrete clarification question (and a draftable email).

## Limitations
- Best-effort PDF/DOCX parsing (no production OCR); pasting text is always reliable.
- Three sample vendors; more would broaden coverage testing.
- No persistence layer or multi-user review workflow.
- The comparison's confidence labels are model-judged, not statistically calibrated.

## What I'd do with more time
- A lightweight **prompt-eval harness**: seed proposals with known defects and assert the extractor catches them (precision/recall on flags).
- **Schema validation** of every agent's JSON against a pydantic model, with auto-repair loops.
- A **human-review** layer where a buyer can accept/override each flag, feeding a correction log back into prompt iteration.
- Side-by-side **prompt versioning** with A/B traces to measure which prompt revision reduces missed flags.
