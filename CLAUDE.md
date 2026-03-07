# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MCP server for Digilent WaveForms instruments (oscilloscope, AWG, logic analyzer). Built with
Python, `fastmcp` v3, and `dwfpy`. Deployed as a Docker image; the proprietary Digilent
libraries (Adept 2 Runtime, `libdwf.so`) are added by users via a derived Dockerfile layer.

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

### Device session lifecycle

`session.py` contains a `DeviceManager` singleton that manages persistent device connections:

- **Auto-connect**: `acquire(device_index)` opens the device on first use, returns the cached
  handle on subsequent calls.
- **Explicit close**: `release(device_index)` closes the device and stops all outputs.
- **Idle timeout**: A 5-minute `threading.Timer` auto-closes idle devices.
- **Thread safety**: All operations are protected by `threading.Lock`.

Tool modules call `get_manager().acquire(device_index)` instead of `with dwf.Device(...)`.
On exception, tools call `get_manager().release(device_index)` to clean up stale handles.

Two session tools (`close_device`, `device_session_status`) are registered in `session_tools.py`.
`server.py` includes a FastMCP lifespan handler that calls `release_all()` on shutdown.

### Mock strategy for tests

All tests live in `tests/test_server.py` (single file) and run without hardware.

**Device tools (devices.py)** — unchanged, mock `dwf` directly:
```python
with patch("dwf_mcp_server.tools.devices.dwf", dwf_mock):
    result = list_devices()
```

**Tools using DeviceManager** — mock `get_manager` to return a manager whose `acquire()`
yields a device mock:
```python
device_mock = MagicMock()
manager_mock = MagicMock()
manager_mock.acquire.return_value = device_mock
with patch("dwf_mcp_server.tools.<module>.get_manager", return_value=manager_mock):
    result = some_tool()
```

**Modules that also use `dwf.Status.DONE`** (analog, digital) need dual-patching:
both `get_manager` and `dwf` are patched simultaneously.

### Error handling convention

Tool functions never raise exceptions to the MCP client. Every tool wraps its body in
`try/except Exception` and returns `{"error": "<message>"}` on failure. The `# noqa: BLE001`
suppresses the ruff broad-exception-caught lint for these intentional catch-all handlers.

### Frequency measurement

`analog._compute_measurement` uses a zero-crossing span algorithm: count zero-crossings in the
sample buffer, measure the time span between first and last crossing, then derive frequency as
`num_half_periods / (2 * time_span)`. This is accurate even with partial periods at buffer edges.

## libdwf Constraint

**Never commit `.so` files to the repository.** The Digilent Adept 2 Runtime and WaveForms SDK
(`libdwf.so`) are proprietary — users install them via a derived Dockerfile layer. The public
Docker image includes only their system-level dependencies (e.g. `libusb-1.0-0`).

## Host / Container Gotchas

- **`/etc/digilent-adept.conf` must exist** — without it, DWF SDK silently fails (device
  enumeration returns empty or hardware control is a no-op despite no errors).
- **USB permissions** — Digilent devices default to `root:root 0664`. Either add a udev rule
  (`ATTRS{idVendor}=="1443", MODE="0666"`) or ensure the user is in the correct group.
- **Docker `--privileged`** is required for USB access; the container's own `/etc/digilent-adept.conf`
  (installed by the Adept .deb) is sufficient — do NOT mount the host's Nix/distro-specific conf.

## Coding Conventions

- **Language**: all GitHub issues, PRs, milestones, and commit messages must be written in English
- **Formatter/linter**: ruff (line-length 100, configured in `pyproject.toml`)
- **Type annotations**: all public functions must have fully-annotated signatures
- **Return types**: MCP tools return `dict` or `list[dict]`
- **Imports**: stdlib → third-party → local, sorted by ruff
- **Pin/channel indexing**: follows hardware labels — no conversion layer
  - **DIO pins** (gpio, spi, digital_capture): **0-based** (0-15), matching DIO0-DIO15
  - **Analog channels** (oscilloscope, AWG): **1-based** (1-2), matching CH1/CH2 and W1/W2

## Release Procedure

1. Update `version` in `pyproject.toml` and `server.json`.
2. Commit, tag `vX.Y.Z`, push with `--tags`.
3. GitHub Actions builds multi-arch image to `ghcr.io/kenosinc/dwf-mcp-server:X.Y.Z` and
   publishes `server.json` to the MCP Registry.
