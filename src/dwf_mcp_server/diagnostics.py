"""Startup environment diagnostics for Docker containers.

Checks DWF SDK prerequisites that cause silent failures when missing.
Only runs inside Docker containers (detected via /.dockerenv).
"""

import logging
import os
import tempfile

import dwfpy as dwf

logger = logging.getLogger(__name__)

ADEPT_CONF_PATH = "/etc/digilent-adept.conf"
FIRMWARE_DIR = "/usr/share/digilent/waveforms/firmware"


def _is_docker() -> bool:
    """Return True if running inside a Docker container."""
    return os.path.isfile("/.dockerenv")


def _parse_adept_conf(path: str) -> dict[str, str]:
    """Parse key=value pairs from digilent-adept.conf."""
    result: dict[str, str] = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    result[key.strip()] = value.strip()
    except OSError as exc:
        logger.error("Cannot read %s: %s", path, exc)
    return result


def check_environment() -> bool:
    """Run startup diagnostics. Returns True if all critical checks pass.

    Critical checks (cause sys.exit if failed):
    - /etc/digilent-adept.conf exists
    - DigilentPath and DigilentDataPath point to valid directories
    - Firmware directory exists and contains .hex files
    - /tmp is writable

    Non-critical checks (warning only):
    - At least one device is enumerable
    """
    if not _is_docker():
        return True

    ok = True

    # --- Critical checks ---

    # 1. Adept config file
    if not os.path.isfile(ADEPT_CONF_PATH):
        logger.error(
            "%s not found. Install Digilent Adept 2 Runtime in your derived Dockerfile.",
            ADEPT_CONF_PATH,
        )
        ok = False
    else:
        conf = _parse_adept_conf(ADEPT_CONF_PATH)

        # 2. DigilentPath
        digilent_path = conf.get("DigilentPath", "")
        if not digilent_path or not os.path.isdir(digilent_path):
            logger.error(
                "DigilentPath=%s is invalid. Check %s.",
                digilent_path,
                ADEPT_CONF_PATH,
            )
            ok = False

        # 3. DigilentDataPath
        data_path = conf.get("DigilentDataPath", "")
        if not data_path or not os.path.isdir(data_path):
            logger.error(
                "DigilentDataPath=%s is invalid. Check %s.",
                data_path,
                ADEPT_CONF_PATH,
            )
            ok = False

    # 4. Firmware directory
    if not os.path.isdir(FIRMWARE_DIR):
        logger.error(
            "%s not found. Install WaveForms SDK in your derived Dockerfile.",
            FIRMWARE_DIR,
        )
        ok = False
    else:
        hex_files = [f for f in os.listdir(FIRMWARE_DIR) if f.endswith(".hex")]
        if not hex_files:
            logger.error(
                "%s contains no .hex files. WaveForms SDK may be incomplete.",
                FIRMWARE_DIR,
            )
            ok = False

    # 5. /tmp writable
    try:
        with tempfile.NamedTemporaryFile(dir="/tmp"):
            pass
    except OSError as exc:
        logger.error(
            "/tmp is not writable (%s). Adept runtime requires /tmp access.",
            exc,
        )
        ok = False

    # --- Non-critical checks ---

    # 6. Device enumeration
    try:
        devices = list(dwf.Device.enumerate())
        if not devices:
            logger.warning("No Digilent WaveForms devices found. Is the device connected?")
    except Exception:  # noqa: BLE001
        logger.warning("Device enumeration failed. libdwf.so may not be installed.")

    return ok
