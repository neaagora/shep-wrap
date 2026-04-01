"""
cli.py — shep-wrap entry point.

Usage:
    shep-wrap [--agent-name NAME] [--out-dir DIR] <command> [args...]

Wraps any subprocess, routes its traffic through a mitmproxy instance, and
writes a shepdog/service-record/v1 JSON record as an involuntary byproduct.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import click

from shep_wrap.schema import make_service_record

# Path to the proxy addon relative to this file
_ADDON_PATH = Path(__file__).parent / "proxy_addon.py"
_MITMPROXY_CERT = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@click.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.option("--agent-name", default=None, help="Override agent_id in the service record.")
@click.option("--out-dir", default=".", show_default=True, help="Directory for service-records output.")
@click.argument("command", nargs=-1, required=True)
def main(agent_name, out_dir, command):
    """Wrap COMMAND, intercept its HTTP traffic, and emit a service record."""
    session_uuid = str(uuid.uuid4())

    # Write session UUID to a temp file; proxy addon will write events there
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="shepdog-", delete=False
    ) as tf:
        session_file = tf.name

    port = _free_port()

    proxy_env = dict(os.environ)
    proxy_env["SHEPDOG_SESSION_FILE"] = session_file

    # Launch mitmdump
    mitmdump_cmd = [
        "mitmdump",
        "--quiet",
        "-p", str(port),
        "--ssl-insecure",
        "-s", str(_ADDON_PATH),
    ]
    try:
        mitmdump_proc = subprocess.Popen(
            mitmdump_cmd,
            env=proxy_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        click.echo("shepdog: mitmdump not found — is mitmproxy installed?", err=True)
        sys.exit(1)

    # Give mitmdump time to bind
    time.sleep(1.5)

    # Build env for the wrapped command
    proxy_url = f"http://127.0.0.1:{port}"
    cmd_env = dict(os.environ)
    cmd_env["SHEPDOG_SESSION_FILE"] = session_file
    cmd_env["HTTP_PROXY"]           = proxy_url
    cmd_env["HTTPS_PROXY"]          = proxy_url
    cmd_env["http_proxy"]           = proxy_url
    cmd_env["https_proxy"]          = proxy_url
    if _MITMPROXY_CERT.exists():
        cmd_env["REQUESTS_CA_BUNDLE"] = str(_MITMPROXY_CERT)
        cmd_env["SSL_CERT_FILE"]      = str(_MITMPROXY_CERT)

    start_time = time.time()

    try:
        result = subprocess.run(
            list(command),
            env=cmd_env,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except FileNotFoundError:
        exe = command[0]
        # Common case: `python` absent but `python3` present
        import shutil
        alt = exe + "3"
        hint = f" (did you mean '{alt}'?)" if shutil.which(alt) else ""
        click.echo(f"shepdog: command not found: {exe!r}{hint}", err=True)
        mitmdump_proc.send_signal(signal.SIGTERM)
        sys.exit(127)

    elapsed = time.time() - start_time

    # Shut down mitmdump gracefully so done() hook fires
    try:
        mitmdump_proc.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        pass

    # Wait up to 3s for the session file to be populated
    deadline = time.time() + 3.0
    events = []
    session_file_written = False
    while time.time() < deadline:
        try:
            raw = Path(session_file).read_text()
            if raw.strip():
                events = json.loads(raw)
                session_file_written = True
                break
        except (OSError, json.JSONDecodeError):
            pass
        time.sleep(0.1)

    if not session_file_written:
        click.echo(
            "shepdog: warning — session file not written within 3s; writing minimal record.",
            err=True,
        )

    # Clean up temp file
    try:
        os.unlink(session_file)
    except OSError:
        pass

    # Build service record
    record = make_service_record(
        model="unknown",
        scenario="cli-wrap",
        task=" ".join(command),
        session_id=session_uuid,
        agent_id=agent_name or Path(command[-1]).stem,
        behavioral_signals={
            "http_request_count": len(events),
            "unique_hosts": len({urlparse(e["url"]).netloc for e in events}),
            "total_latency_ms": sum(e.get("latency_ms", 0) for e in events),
        },
        event_log=events,
        verdict="UNKNOWN",
        verdict_reason=(
            "shep-wrap v1: traffic recorded, verdict requires scenario-aware evaluation"
        ),
        duration_seconds=elapsed,
    )

    # Write record
    out_path = Path(out_dir) / "service-records"
    out_path.mkdir(parents=True, exist_ok=True)
    record_file = out_path / f"{session_uuid}.json"
    record_file.write_text(json.dumps(record, indent=2))

    click.echo(
        f"shepdog: {len(events)} requests intercepted → "
        f"record written to service-records/{session_uuid[:8]}.json",
        err=True,
    )

    sys.exit(result.returncode)
