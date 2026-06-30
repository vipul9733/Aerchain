"""
Generate the shipped sample dataset by actually running the prompts.
Produces:
  data/rfq.json
  data/vendors.json           (raw generated vendor proposals)
  data/extractions.json       (extraction agent output per vendor)
  data/comparison.json        (comparison agent output)
  data/uiux_spec.json         (UI/UX agent output)
  data/traces.json            (full prompt traces for the Prompt Trace deliverable)

Run once with an API key set:  python generate_sample_data.py
The Streamlit app loads these by default so the demo is instant, but every
screen can also regenerate live.
"""

import json
import os
from dataclasses import asdict

from agents import agents
from prompts import prompt_pack as pp

DATA = os.path.join(os.path.dirname(__file__), "data")


def main():
    os.makedirs(DATA, exist_ok=True)
    traces = []

    print("1/5  Generating RFQ ...")
    rfq = agents.generate_rfq(traces)
    json.dump(rfq, open(f"{DATA}/rfq.json", "w"), indent=2)
    line_items = [li["name"] for li in rfq.get("line_items", [])]

    print("2/5  Generating vendor responses ...")
    vendors = []
    for preset in pp.VENDOR_PRESETS:
        print(f"      - {preset['name']}")
        vendors.append(agents.generate_vendor_response(rfq, preset, traces))
    json.dump(vendors, open(f"{DATA}/vendors.json", "w"), indent=2)

    print("3/5  Extracting from each vendor ...")
    extractions = []
    for v in vendors:
        print(f"      - {v['vendor_name']}")
        extractions.append(agents.extract_vendor(v["vendor_name"], v["text"], line_items, traces))
    json.dump(extractions, open(f"{DATA}/extractions.json", "w"), indent=2)

    print("4/5  Comparing vendors ...")
    comparison = agents.compare_vendors(extractions, traces)
    json.dump(comparison, open(f"{DATA}/comparison.json", "w"), indent=2)

    print("5/5  Generating UI/UX spec ...")
    uiux = agents.generate_uiux(traces)
    json.dump(uiux, open(f"{DATA}/uiux_spec.json", "w"), indent=2)

    json.dump([asdict(t) for t in traces], open(f"{DATA}/traces.json", "w"), indent=2)
    print(f"\nDone. {len(traces)} traces captured. Files written to {DATA}/")


if __name__ == "__main__":
    main()
