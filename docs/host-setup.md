# Host Setup: libdwf Installation & AD3 Verification

Step-by-step guide to install the WaveForms SDK on the host
machine and verify that an Analog Discovery 3 (AD3) is recognized
and usable by `dwf-mcp-server`.

> **Note:** The Docker image bundles the WaveForms SDK (`libdwf.so`)
> and Adept 2 Runtime. No host-side installation is needed for
> Docker usage. The steps below are only needed for **local
> (non-Docker) development**.

## 1. Install WaveForms SDK

### Linux (Debian/Ubuntu)

Download the latest `.deb` package from the
[Digilent WaveForms download page](https://digilent.com/reference/software/waveforms/waveforms-3/start),
then install:

```bash
sudo dpkg -i digilent.waveforms_*.deb
sudo apt-get install -f   # resolve dependencies if needed
```

### NixOS

If you are using NixOS, the libraries are available under the system profile:

```text
/run/current-system/sw/lib/libdwf.so
/run/current-system/sw/lib/libdmgr.so.2
/run/current-system/sw/lib/libdmgt.so.2
/run/current-system/sw/lib/libdjtg.so.2
```

### Verify libdwf

Confirm `libdwf.so` is present (Adept Runtime dependencies are installed
inside the Docker image, so only `libdwf.so` needs to exist on the host):

```bash
ls -l /usr/lib/libdwf.so
```

On NixOS, check `/run/current-system/sw/lib/libdwf.so` instead.

## 2. Connect and Check USB Device

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

## 3. Quick Smoke Test with Python (no Docker)

In a virtual environment with `dwfpy` installed:

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

## 4. Run dwf-mcp-server Locally (no Docker)

```bash
cd /path/to/dwf-mcp-server
uv pip install -e ".[dev]"
dwf-mcp-server
# Server should start on stdio without errors
```

## 5. Run via Docker

```bash
docker run -i --rm --privileged ghcr.io/kenosinc/dwf-mcp-server
```

## 6. Verify with list_devices MCP Tool

Call `list_devices` via your MCP client and confirm the AD3 appears in the response.

## Checklist

- [ ] `lsusb` shows the AD3
- [ ] `docker run --privileged ghcr.io/kenosinc/dwf-mcp-server` starts without errors
- [ ] `list_devices` tool returns the AD3 info
