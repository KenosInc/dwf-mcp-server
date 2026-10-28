# Security Policy

## Reporting a vulnerability

Please report security issues privately via
[GitHub Security Advisories](https://github.com/KenosInc/dwf-mcp-server/security/advisories/new).
Do not open a public issue for anything you believe is exploitable.

We aim to acknowledge reports within 7 days.

## Scope and threat model

This server drives real test instruments (power supply, waveform generator,
GPIO). Tool calls originate from an LLM, so a malicious or confused prompt can
translate directly into voltages applied to a device under test. Treat the
MCP client, the model, and anything the model reads (including data captured
from the DUT) as untrusted input.

Only run this server against hardware you are prepared to damage, and prefer
the least-privileged container configuration documented in the README
(`--device=/dev/bus/usb` rather than `--privileged`).

## Supply chain

- GitHub Actions are pinned to commit SHAs and updated by Dependabot.
- Runtime dependencies are locked in `uv.lock` and audited with `pip-audit` in CI.
- Published container images carry SLSA provenance and an SBOM.
