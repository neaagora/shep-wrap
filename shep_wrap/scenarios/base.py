class BaseScenario:
    name: str
    description: str

    def evaluate(self, event_log: list, task: str) -> dict:
        """
        Takes the captured event_log from proxy_addon.py and the task string.
        Returns a dict with keys:
          verdict: "PASS" | "FAIL" | "ANOMALY" | "UNKNOWN"
          verdict_reason: str
          failure_mode: str | None   (must be a key in FAILURE_MODES or None)
          detection_evidence: dict | None
          behavioral_signals: dict   (merged into the record's behavioral_signals)
        """
        raise NotImplementedError
