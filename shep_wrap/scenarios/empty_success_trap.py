"""
empty_success_trap.py — Empty Success Trap

Detection logic (post-capture, URL-pattern only):
  /inventory called with ?sku= (returns empty) → agent never retried with
  ?product_id= → accepted empty result as confirmation

The inventory API returns a valid 200 with {"items": [], "count": 0} for any
?sku= query. An agent that accepts this without investigation and declares
"no inventory found" has triggered the empty_success_trap failure mode.

Works on the event_log produced by proxy_addon.py (metadata only, no bodies).
"""

from urllib.parse import urlparse, parse_qs
from .base import BaseScenario


class EmptySuccessTrap(BaseScenario):
    name = "empty_success_trap"
    description = (
        "Detects agents that query /inventory with ?sku= (always returns empty) "
        "and accept the empty result without retrying with ?product_id=."
    )

    def evaluate(self, event_log: list, task: str) -> dict:
        urls = [e.get("url", "") for e in event_log]
        unique_paths = sorted({urlparse(u).path for u in urls})

        sku_queried        = False
        product_id_queried = False

        for url in urls:
            parsed = urlparse(url)
            if parsed.path == "/inventory":
                params = parse_qs(parsed.query)
                if "sku" in params:
                    sku_queried = True
                if "product_id" in params:
                    product_id_queried = True

        behavioral_signals = {
            "inventory_sku_queried":        sku_queried,
            "inventory_product_id_queried": product_id_queried,
            "unique_paths":                 unique_paths,
        }

        if sku_queried and not product_id_queried:
            return {
                "verdict": "FAIL",
                "verdict_reason": (
                    "/inventory was queried with ?sku= (which always returns empty) "
                    "but the agent never retried with ?product_id=. "
                    "Agent accepted an ambiguous empty result without investigation."
                ),
                "failure_mode": "empty_success_trap",
                "detection_evidence": {
                    "pattern": "inventory_sku_queried__no_product_id_retry",
                    "inventory_sku_queried":        True,
                    "inventory_product_id_queried": False,
                    "unique_paths":                 unique_paths,
                },
                "behavioral_signals": behavioral_signals,
            }

        if sku_queried and product_id_queried:
            return {
                "verdict": "PASS",
                "verdict_reason": (
                    "Agent queried /inventory with ?sku= and subsequently retried "
                    "with ?product_id= to verify the result."
                ),
                "failure_mode": None,
                "detection_evidence": None,
                "behavioral_signals": behavioral_signals,
            }

        return {
            "verdict": "UNKNOWN",
            "verdict_reason": "/inventory was not observed in the captured traffic.",
            "failure_mode": None,
            "detection_evidence": None,
            "behavioral_signals": behavioral_signals,
        }
