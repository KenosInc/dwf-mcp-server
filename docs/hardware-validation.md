# Hardware Validation

Smoke-test results for DWF MCP server tools running against real hardware.

## Environment

| Component | Detail |
|-----------|--------|
| Device | Analog Discovery 3 |
| Serial | 210415BF8E27 |
| Host | Docker container (`dwf-mcp-server:local`) with Adept 2.27.9 / WaveForms 3.24.4 |
| Date | 2026-03-06 |

## list_devices

```json
[
  {
    "index": 0,
    "name": "Analog Discovery 3",
    "serial": "210415BF8E27",
    "is_open": 0
  }
]
```

Result: PASS — device detected with correct name and serial number.

## device_info

```json
{
  "index": 0,
  "name": "Analog Discovery 3",
  "serial": "210415BF8E27",
  "is_open": 0
}
```

Result: PASS — detailed device information returned successfully.
