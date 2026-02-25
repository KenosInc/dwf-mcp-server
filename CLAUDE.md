# CLAUDE.md — dwf-mcp-server

Development guide for AI agents and contributors.

## Project Structure

```
dwf-mcp-server/
├── src/dwf_mcp_server/
│   ├── server.py          # FastMCP server entry point
│   └── tools/
│       ├── devices.py     # list_devices, device_info
│       ├── analog.py      # analog_capture, generate_waveform, measure
│       └── digital.py     # digital_capture
├── tests/
│   └── test_server.py     # Unit tests (no hardware required)
├── pyproject.toml
├── Dockerfile
└── .github/workflows/
    ├── ci.yml
    ├── docker-publish.yml
    └── mcp-registry.yml
```

## libdwf Handling

**libdwf is proprietary and must NOT be committed or bundled in the Docker image.**

- All tools import `dwfpy` inside the function body (`import dwfpy as dwf`) to defer the
  library load until the tool is actually called.
- When `libdwf.so` is not mounted, tools catch `OSError` and return a descriptive error dict
  instead of raising an exception.
- Never add `libdwf.so` or related `.so` files to the repository.

## Coding Conventions

- **Formatter / linter**: [ruff](https://docs.astral.sh/ruff/) — run `ruff format .` and
  `ruff check .` before committing.
- **Type annotations**: All public functions must have fully-annotated signatures.
- **Return types**: MCP tools return `dict` or `list[dict]`. On error, always return
  `{"error": "<message>"}` rather than raising an exception.
- **Line length**: 100 characters (configured in `pyproject.toml`).
- **Imports**: Standard library → third-party → local; sorted by ruff (`isort` compatible).

## Testing

Tests live in `tests/test_server.py` and must run without real hardware.

- `dwfpy` is mocked via `unittest.mock.patch.dict("sys.modules", {"dwfpy": mock})`.
- Each tool module exposes its functions at module level so tests can call them directly
  without going through FastMCP.
- Run tests:
  ```bash
  uv pip install -e ".[dev]"
  pytest tests/ -v
  ```
- Run lint:
  ```bash
  ruff format --check .
  ruff check .
  ```

## Build & Run

```bash
# Install for local development
uv pip install -e ".[dev]"

# Run server (stdio)
dwf-mcp-server

# Build Docker image
docker build -t dwf-mcp-server .

# Run container (libdwf from host)
docker run -i --rm \
  -v /usr/lib/libdwf.so:/usr/lib/libdwf.so \
  -v /usr/lib/libdmgr.so.2:/usr/lib/libdmgr.so.2 \
  -v /usr/lib/libdmgt.so.2:/usr/lib/libdmgt.so.2 \
  -v /usr/lib/libdjtg.so.2:/usr/lib/libdjtg.so.2 \
  --privileged \
  dwf-mcp-server
```

## Release Procedure

1. Update `version` in `pyproject.toml` and `server.json`.
2. Commit: `git commit -m "chore: bump version to X.Y.Z"`
3. Tag: `git tag vX.Y.Z`
4. Push: `git push origin main --tags`
5. GitHub Actions automatically:
   - Builds and pushes multi-arch image to `ghcr.io/kenosinc/dwf-mcp-server:X.Y.Z`
   - Publishes updated `server.json` to the MCP Registry
