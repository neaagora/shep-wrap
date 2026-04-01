"""
proxy_addon.py — mitmproxy addon for shepdog traffic interception.

Records HTTP request/response metadata (no bodies) to a session file whose
path is read from SHEPDOG_SESSION_FILE at startup.
"""

import json
import os
import time

from mitmproxy import http


class ShepdogAddon:
    def __init__(self):
        self._events: list[dict] = []
        # Map (method, url) → index in _events for latency correlation
        self._pending: dict[tuple, int] = {}

    def request(self, flow: http.HTTPFlow) -> None:
        seq = len(self._events) + 1
        entry = {
            "seq": seq,
            "ts": flow.request.timestamp_start,
            "method": flow.request.method,
            "url": flow.request.pretty_url,
            "request_size": len(flow.request.raw_content or b""),
        }
        key = (flow.request.method, flow.request.pretty_url)
        self._pending[key] = len(self._events)
        self._events.append(entry)

    def response(self, flow: http.HTTPFlow) -> None:
        key = (flow.request.method, flow.request.pretty_url)
        idx = self._pending.pop(key, None)
        if idx is None:
            return
        latency_ms = (flow.response.timestamp_end - flow.request.timestamp_start) * 1000
        self._events[idx].update({
            "status_code": flow.response.status_code,
            "response_size": len(flow.response.raw_content or b""),
            "latency_ms": round(latency_ms, 2),
        })

    def done(self) -> None:
        session_file = os.environ.get("SHEPDOG_SESSION_FILE")
        if not session_file:
            return
        try:
            with open(session_file, "w") as fh:
                json.dump(self._events, fh)
        except OSError as exc:
            print(f"shepdog proxy_addon: failed to write session file: {exc}", flush=True)


addons = [ShepdogAddon()]
