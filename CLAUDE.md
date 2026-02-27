# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MCP server for Digilent WaveForms instruments (oscilloscope, AWG, logic analyzer). Built with
Python, `fastmcp` v3, and `dwfpy`. Deployed as a Docker image; the proprietary `libdwf.so` is
volume-mounted from the host at runtime.

## Commands

```bash
# GitHub milestone operations (no `gh milestone` command exists)
gh api repos/{owner}/{repo}/milestones                                       # list
gh api repos/{owner}/{repo}/milestones -f title="..." -f description="..."   # create

# Install for development
uv pip install -e ".[dev]"

# Run all tests (no hardware required)
pytest tests/ -v

# Run a single test class or method
pytest tests/test_server.py::TestComputeMeasurement -v
pytest tests/test_server.py::TestListDevices::test_returns_device_list -v

# Lint & format
ruff format --check .
ruff check .
ruff format .          # auto-fix formatting
ruff check --fix .     # auto-fix lint issues

# Run server locally (requires libdwf on host)
dwf-mcp-server
```

## Architecture

### Tool registration pattern

Each tool module in `src/dwf_mcp_server/tools/` follows the same pattern:

1. Module-level functions with full type annotations — these are the actual MCP tools.
2. A `register(mcp: FastMCP)` function at the bottom that calls `mcp.tool(fn)` for each tool.
3. `server.py` imports each module and calls `module.register(mcp)`.

This design keeps tool functions callable directly (for testing) while letting `server.py` be the
single registration point.

### Mock strategy for tests

All tests live in `tests/test_server.py` (single file) and run without hardware. Each tool module does `import dwfpy as dwf` at the top level.
Tests mock the entire `dwf` namespace per-module:

```python
with patch("dwf_mcp_server.tools.devices.dwf", dwf_mock):
    result = list_devices()
```

The mock target is always `dwf_mcp_server.tools.<module>.dwf`, not the global `dwfpy`.

### Error handling convention

Tool functions never raise exceptions to the MCP client. Every tool wraps its body in
`try/except Exception` and returns `{"error": "<message>"}` on failure. The `# noqa: BLE001`
suppresses the ruff broad-exception-caught lint for these intentional catch-all handlers.

### Frequency measurement

`analog._compute_measurement` uses a zero-crossing span algorithm: count zero-crossings in the
sample buffer, measure the time span between first and last crossing, then derive frequency as
`num_half_periods / (2 * time_span)`. This is accurate even with partial periods at buffer edges.

## libdwf Constraint

**libdwf is proprietary — never commit `.so` files or bundle them in the Docker image.**

Tool modules import `dwfpy` at the top level. If `libdwf.so` is missing, the server fails at
startup — this is intentional for container deployments (users must volume-mount the library).

## Coding Conventions

- **Language**: all GitHub issues, PRs, milestones, and commit messages must be written in English
- **Formatter/linter**: ruff (line-length 100, configured in `pyproject.toml`)
- **Type annotations**: all public functions must have fully-annotated signatures
- **Return types**: MCP tools return `dict` or `list[dict]`
- **Imports**: stdlib → third-party → local, sorted by ruff
- **Channel indexing**: MCP tools accept 1-based channel numbers; convert to 0-based (`ch_idx = channel - 1`) before passing to `dwfpy`

## Release Procedure

1. Update `version` in `pyproject.toml` and `server.json`.
2. Commit, tag `vX.Y.Z`, push with `--tags`.
3. GitHub Actions builds multi-arch image to `ghcr.io/kenosinc/dwf-mcp-server:X.Y.Z` and
   publishes `server.json` to the MCP Registry.
