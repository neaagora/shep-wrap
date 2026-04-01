# shep-wrap

A pip-installable CLI that wraps any agent subprocess and generates a
`shepdog/service-record/v1` record as an **involuntary** byproduct of
execution. Zero changes to the wrapped agent required.

## Installation

```bash
pip install -e .
```

mitmproxy must be installed and `mitmdump` must be on your PATH.

## Usage

```bash
# Wrap an agent and record its HTTP traffic
shep-wrap python your_agent.py

# Override the agent name in the record
shep-wrap --agent-name my-agent python your_agent.py

# Write records to a custom directory
shep-wrap --out-dir /tmp/runs python your_agent.py

# View a summary of collected records
shepdog report

# Dump aggregated data as JSON
shepdog report --json
```

## How it works

1. A session UUID is generated.
2. A free local port is found and `mitmdump` is started on it with the
   `proxy_addon.py` mitmproxy addon loaded.
3. The wrapped command is launched with `HTTP_PROXY`, `HTTPS_PROXY`, and
   `REQUESTS_CA_BUNDLE` injected into its environment so all outbound HTTP/S
   traffic flows through the proxy.
4. After the command exits, mitmdump is sent SIGTERM (triggering the `done()`
   hook which flushes the session buffer).
5. A `shepdog/service-record/v1` JSON record is written to
   `<out-dir>/service-records/<session-id>.json`.
6. A one-line summary is printed to **stderr** only — stdout is never touched.

## Output record

Records follow the `shepdog/service-record/v1` schema. The `verdict` field is
always `UNKNOWN` in v1 because shep-wrap records traffic only; scenario-aware
evaluation is future work.

## SSL / TLS caveat

shep-wrap passes `--ssl-insecure` to mitmdump so agents using self-signed
certificates continue to work. Agents that perform **strict SSL/TLS pinning**
will reject the mitmproxy certificate and bypass the proxy transparently —
their traffic will not appear in the service record. This is an honest
limitation of the approach, not a bug.

To intercept TLS traffic from agents that do trust the system certificate
store, install the mitmproxy CA certificate:

```bash
# macOS
security add-trusted-cert -d -r trustRoot \
    -k /Library/Keychains/System.keychain ~/.mitmproxy/mitmproxy-ca-cert.pem

# Linux (varies by distro)
cp ~/.mitmproxy/mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/mitmproxy-ca.crt
update-ca-certificates
```

## observer_independence

`observer_independence: "involuntary"` is a fixed, non-overridable field
enforced by `schema.py`. Records are structural byproducts of mediation, not
self-disclosure by the agent under observation.
