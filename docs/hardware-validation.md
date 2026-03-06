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

## digital_capture

### Setup

External bench power supply (3.3 V) connected to DIO4; DIO5 wired to GND.
Common ground shared between power supply and AD3.

### Test 1 — Baseline (floating)

Channels 4 and 5 with no connections (prior to wiring the power supply).

```json
{
  "channels": [4, 5],
  "sample_rate": 1000000,
  "duration": 0.001,
  "sample_count": 1000,
  "samples": [0, 0, "... (all 0)"]
}
```

Result: PASS — all 1000 samples are 0 (both channels LOW when floating).

### Test 2 — Static loopback (V+ → DIO4, GND → DIO5)

```json
{
  "channels": [4, 5],
  "sample_rate": 1000000,
  "duration": 0.001,
  "sample_count": 1000,
  "samples": [16, 16, "... (all 16)"]
}
```

Each sample = `16` = `0b10000` → bit 4 (CH4) = HIGH, bit 5 (CH5) = LOW.

Result: PASS — DIO4 reads HIGH (3.3 V), DIO5 reads LOW (GND).

### Test 3 — Channel mask (CH4 only)

```json
{
  "channels": [4],
  "sample_count": 1000,
  "samples": [16, 16, "... (all 16)"]
}
```

Result: PASS — only CH4 bit present, reads HIGH.

### Test 4 — Channel mask (CH5 only)

```json
{
  "channels": [5],
  "sample_count": 1000,
  "samples": [0, 0, "... (all 0)"]
}
```

Result: PASS — only CH5 bit present, reads LOW.
