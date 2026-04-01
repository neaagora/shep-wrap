"""
report.py — shepdog report entry point.

Usage:
    shepdog report [--dir DIR] [--json]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import click


@click.group()
def main():
    """shepdog — service record reporter."""


@main.command("report")
@click.option("--dir", "search_dir", default=".", show_default=True,
              help="Directory containing service-records/")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Dump aggregated data as JSON instead of a human-readable table.")
def report(search_dir, as_json):
    """Summarise service records found under DIR/service-records/."""
    records_dir = Path(search_dir) / "service-records"
    files = sorted(records_dir.glob("*.json")) if records_dir.is_dir() else []

    if not files:
        click.echo(f"No service records found in {records_dir}", err=True)
        sys.exit(0)

    # Group by agent_id
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for fpath in files:
        try:
            record = json.loads(fpath.read_text())
            by_agent[record.get("agent_id", "unknown")].append(record)
        except (OSError, json.JSONDecodeError) as exc:
            click.echo(f"shepdog: skipping {fpath.name}: {exc}", err=True)

    if as_json:
        aggregated = {}
        for agent_id, records in sorted(by_agent.items()):
            verdicts: dict[str, int] = defaultdict(int)
            total_requests = 0
            all_hosts: set[str] = set()
            for r in records:
                verdicts[r.get("verdict", "UNKNOWN")] += 1
                sigs = r.get("behavioral_signals", {})
                total_requests += sigs.get("http_request_count", 0)
                # Reconstruct hosts from event_log if present
                for ev in r.get("event_log", []):
                    url = ev.get("url", "")
                    if url:
                        from urllib.parse import urlparse
                        netloc = urlparse(url).netloc
                        if netloc:
                            all_hosts.add(netloc)
            aggregated[agent_id] = {
                "session_count": len(records),
                "verdicts": dict(verdicts),
                "total_requests": total_requests,
                "avg_requests_per_session": round(total_requests / len(records), 1),
                "unique_hosts": sorted(all_hosts),
            }
        click.echo(json.dumps(aggregated, indent=2))
        return

    # Human-readable table
    for agent_id, records in sorted(by_agent.items()):
        n = len(records)
        verdicts: dict[str, int] = defaultdict(int)
        total_requests = 0
        all_hosts: set[str] = set()

        for r in records:
            verdicts[r.get("verdict", "UNKNOWN")] += 1
            sigs = r.get("behavioral_signals", {})
            total_requests += sigs.get("http_request_count", 0)
            for ev in r.get("event_log", []):
                url = ev.get("url", "")
                if url:
                    from urllib.parse import urlparse
                    netloc = urlparse(url).netloc
                    if netloc:
                        all_hosts.add(netloc)

        verdict_str = ", ".join(
            f"{v} x{c}" for v, c in sorted(verdicts.items())
        )
        avg_req = round(total_requests / n, 1)
        hosts_str = ", ".join(sorted(all_hosts)) if all_hosts else "(none)"

        click.echo(f"Agent: {agent_id} ({n} session{'s' if n != 1 else ''})")
        click.echo(f"  Verdicts:  {verdict_str}")
        click.echo(f"  Requests:  avg {avg_req}/session, total {total_requests}")
        click.echo(f"  Hosts:     {hosts_str}")
        click.echo()
