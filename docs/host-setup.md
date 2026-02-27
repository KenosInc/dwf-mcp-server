# Host Setup: AD3 Verification

Step-by-step guide to verify that an Analog Discovery 3 (AD3) is recognized
and usable by `dwf-mcp-server`.

> **Note:** The Digilent Adept 2 Runtime and WaveForms SDK (`libdwf.so`) are
> proprietary and not included in the public Docker image. Users add them by
> building a derived Dockerfile — see the [README](../README.md#installation)
> for instructions.

## 1. Connect and Check USB Device

Plug in the AD3, then verify it appears on the USB bus:

```bash
lsusb | grep -i digilent
# Expected: Bus xxx Device yyy: ID 0403:6014 ...
```

Ensure the current user has USB access:

```bash
# Option A: add user to the plugdev group (recommended)
sudo usermod -aG plugdev $USER
# Log out and log back in for the group change to take effect

# Option B: run with sudo (not recommended for production)
```

## 2. Quick Smoke Test with Python (no Docker)

Install the WaveForms SDK on the host, then in a virtual environment with `dwfpy`:

```bash
python3 -c "
import dwfpy as dwf
devices = dwf.Device.enumerate()
print(f'Found {len(devices)} device(s)')
for d in devices:
    print(f'  {d.name}  SN:{d.serial_number}')
"
```

You should see at least one device listed.

## 3. Run dwf-mcp-server Locally (no Docker)

```bash
cd /path/to/dwf-mcp-server
uv pip install -e ".[dev]"
dwf-mcp-server
# Server should start on stdio without errors
```

## 4. Run via Docker (Derived Image)

First, build a derived image with the Adept 2 Runtime and WaveForms SDK — see
[README](../README.md#installation).

```bash
docker run -i --rm --privileged dwf-mcp-server
```

## 5. Verify with list_devices MCP Tool

Call `list_devices` via your MCP client and confirm the AD3 appears in the response.

## Checklist

- [ ] `lsusb` shows the AD3
- [ ] `dwfpy` enumerate returns at least 1 device
- [ ] `dwf-mcp-server` starts without import errors
- [ ] `list_devices` tool returns the AD3 info
