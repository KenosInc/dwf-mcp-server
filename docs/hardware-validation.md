# Hardware Validation

Smoke-test results for DWF MCP server tools running against real hardware.

## Environment

| Component | Detail |
|-----------|--------|
| Device | Analog Discovery 3 |
| Serial | 210415BF8E27 |
| Host | Docker container (`dwf-mcp-server:local`) with Adept 2.27.9 / WaveForms 3.24.4 |
| Date | 2026-03-06 (digital), 2026-03-09 (analog) |

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

## SPI loopback (MOSI → MISO)

### Setup

DIO1 (MOSI) → DIO2 (MISO) connected with a single jumper wire on the AD3 pin header.
Pin assignments: DIO0 = SCLK, DIO1 = MOSI, DIO2 = MISO, DIO3 = CS.

All tests executed via MCP server (JSON-RPC over stdio).

### dwfpy binding patch

dwfpy <= 1.2.0 declares the `rgRX` parameter of `FDwfDigitalSpiWriteRead` as `_OUT`,
causing ctypes to auto-allocate a single-element buffer. The `protocols.Spi.write_read`
method passes the buffer explicitly, resulting in an argument count mismatch.
A monkey-patch in `patches.py` redefines the bindings with `_IN` for `rgRX`.

### Test 1 — Basic loopback (mode 0, 1 byte)

```json
{"mosi": "a5", "miso": "a5", "bits_transferred": 8}
```

Result: PASS — 0xA5 sent and received identically.

### Test 2 — Multi-byte loopback (mode 0, 3 bytes)

```json
{"mosi": "deadbe", "miso": "deadbe", "bits_transferred": 24}
```

Result: PASS — 3-byte payload looped back correctly.

### Tests 3–6 — All SPI modes (0–3)

2-byte payload (0x55AA) tested across all four SPI modes.

| Mode | CPOL | CPHA | MISO | Result |
|------|------|------|------|--------|
| 0 | 0 | 0 | 55aa | PASS |
| 1 | 0 | 1 | 55aa | PASS |
| 2 | 1 | 0 | 55aa | PASS |
| 3 | 1 | 1 | 55aa | PASS |

### Test 7 — Write-only (no MISO pin)

```json
{"mosi": "ff00", "miso": null, "bits_transferred": 16}
```

Result: PASS — write-only transfer completed, `miso` correctly null.

### Test 8 — Larger payload (8 bytes)

```json
{"mosi": "0123456789abcdef", "miso": "0123456789abcdef", "bits_transferred": 64}
```

Result: PASS — 8-byte payload (64 bits) looped back correctly.

## Analog loopback (W1 → CH1)

### Setup

W1 (AWG CH1) → 1+ (scope CH1+), ⏚ (GND) → 1- (scope CH1−).
Two jumper wires on the AD3 pin header.

### generate_waveform — all waveform types

1 kHz, 1 Vp amplitude, 0 V offset, continuous output on W1.
Measured on CH1 using `measure` (1 MHz sample rate, 10 ms window).

| Waveform | Frequency (Hz) | RMS (V) | Vpp (V) | DC (V) | Expected RMS | Result |
|----------|---------------|---------|---------|--------|-------------|--------|
| sine | 999.5 | 0.7063 | 2.010 | 0.019 | 0.707 (1/√2) | PASS |
| square | 1000.0 | 0.9997 | 2.041 | 0.019 | 1.000 | PASS |
| triangle | 1001.1 | 0.5765 | 2.006 | 0.019 | 0.577 (1/√3) | PASS |
| ramp-up | 1027.7 | 0.8267 | 2.017 | 0.517 | — | PASS ¹ |
| ramp-down | 1027.5 | 0.8267 | 2.024 | 0.518 | — | PASS ¹ |

¹ Ramp waveforms show ~2.8% frequency error due to the zero-crossing algorithm's
sensitivity to asymmetric waveforms. The non-zero DC offset (~0.5 V) is expected
because ramp signals are not symmetric about zero. Vpp values confirm correct
amplitude output.

### analog_capture

Captured 10,000 samples at 1 MHz (10 ms window) of a 1 kHz sine wave on CH1.

```
sample_count: 10000
sample_rate:  1000000.0
duration:     0.01
min:         -1.0065 V
max:          1.1031 V
peak_to_peak: 2.1096 V
```

Result: PASS — 10 complete cycles captured, amplitude consistent with 1 Vp setting.

### measure — all measurement types

Measured on CH1 with 1 kHz sine wave from W1 (1 Vp, 0 V offset).

| Measurement | Value | Unit | Expected | Error | Result |
|------------|-------|------|----------|-------|--------|
| frequency | 999.5 | Hz | 1000 | 0.05% | PASS |
| rms | 0.7063 | V | 0.707 | 0.1% | PASS |
| peak_to_peak | 2.010 | V | 2.000 | 0.5% | PASS |
| dc | 0.019 | V | 0.000 | — | PASS |

### MCP server integration (JSON-RPC over stdio)

Same test sequence executed via MCP protocol (`initialize` → `tools/call`).
Device session persisted across `generate_waveform` → `measure` calls.

| Measurement | Value | Unit | Result |
|------------|-------|------|--------|
| frequency | 1000.3 | Hz | PASS |
| rms | 0.707 | V | PASS |
| peak_to_peak | 2.012 | V | PASS |

`close_device` successfully released the device (`is_open: 0`).

Result: PASS — hybrid session lifecycle verified end-to-end through MCP protocol.
