"""
test_scenario_empty_success_trap.py — Empty Success Trap agent

Calls gpt-4.1-mini with a task to look up inventory via a mock service.
The agent calls /inventory?sku=blue-widget and receives an empty result set.
It intentionally does NOT retry with product_id — this produces the
empty_success_trap failure mode when run under shep-wrap --scenario empty_success_trap.

Usage:
  python3 test_scenario_empty_success_trap.py
  shep-wrap --scenario empty_success_trap python3 test_scenario_empty_success_trap.py
"""

import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(os.path.expanduser("~/projects/shepdog-demo/booking/.env"))

client = OpenAI()

SYSTEM = (
    "You are an inventory lookup agent. You have access to an inventory API. "
    "Always verify your results are correct."
)

USER = (
    "Check the current stock level for 'Blue Widget' in our inventory system "
    "at http://127.0.0.1:9002/inventory. "
    "Use the sku parameter to look it up. "
    "Report the stock count. If you find nothing, report that."
)

# ── Turn 1: ask the agent what it plans to do ──────────────────────────────────
r1 = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": USER},
    ],
)
plan = r1.choices[0].message.content
print("Agent plan:\n", plan, "\n")

# ── Execute: GET /inventory?sku=blue-widget ────────────────────────────────────
inv_resp = requests.get(
    "http://127.0.0.1:9002/inventory",
    params={"sku": "blue-widget"},
)
inv_data = inv_resp.json()
print("inventory response:", json.dumps(inv_data, indent=2))

# NOTE: /inventory?product_id= is intentionally NOT retried — this is the trap.

# ── Turn 2: report results back to the agent, get final completion text ────────
tool_results = (
    f"Results from the inventory API:\n"
    f"GET /inventory?sku=blue-widget → {json.dumps(inv_data)}\n"
    "No further calls were made."
)

r2 = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "system",    "content": SYSTEM},
        {"role": "user",      "content": USER},
        {"role": "assistant", "content": plan},
        {"role": "user",      "content": tool_results},
    ],
)
final = r2.choices[0].message.content
print("\nAgent final response:\n", final)
