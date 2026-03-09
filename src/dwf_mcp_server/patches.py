"""Monkey-patches for dwfpy binding bugs.

dwfpy <= 1.2.0 declares the rgRX parameter of FDwfDigitalSpiWriteRead,
FDwfDigitalSpiRead, and their 16-/32-bit variants as ``_OUT``, which makes
ctypes auto-allocate a single-element buffer and return it as the function
result.  ``protocols.Spi.write_read`` and ``protocols.Spi.read`` pass the
buffer explicitly, resulting in an argument count mismatch.

See: https://github.com/mariusgreuel/dwfpy/issues/10

Redefining these bindings with ``_IN`` for rgRX fixes the mismatch so that
``protocols.py`` can pass the caller-allocated receive buffer directly.
"""

import logging
from ctypes import POINTER, c_int, c_ubyte, c_uint, c_ushort

import dwfpy.bindings as _bindings

logger = logging.getLogger(__name__)

_IN = 1  # ctypes paramflag: input parameter
HDWF = _bindings.HDWF


def apply() -> None:
    """Patch dwfpy SPI read and write_read bindings (idempotent)."""
    _patch = _bindings._dwf_function  # noqa: SLF001

    # --- SPI read (rx-only) ---

    _bindings.dwf_digital_spi_read = _patch(
        "FDwfDigitalSpiRead",
        (_IN, HDWF, "hdwf"),
        (_IN, c_int, "cDQ"),
        (_IN, c_int, "cBitPerWord"),
        (_IN, POINTER(c_ubyte), "rgRX"),
        (_IN, c_int, "cRX"),
    )

    _bindings.dwf_digital_spi_read16 = _patch(
        "FDwfDigitalSpiRead16",
        (_IN, HDWF, "hdwf"),
        (_IN, c_int, "cDQ"),
        (_IN, c_int, "cBitPerWord"),
        (_IN, POINTER(c_ushort), "rgRX"),
        (_IN, c_int, "cRX"),
    )

    _bindings.dwf_digital_spi_read32 = _patch(
        "FDwfDigitalSpiRead32",
        (_IN, HDWF, "hdwf"),
        (_IN, c_int, "cDQ"),
        (_IN, c_int, "cBitPerWord"),
        (_IN, POINTER(c_uint), "rgRX"),
        (_IN, c_int, "cRX"),
    )

    # --- SPI write_read (tx + rx) ---

    _bindings.dwf_digital_spi_write_read = _patch(
        "FDwfDigitalSpiWriteRead",
        (_IN, HDWF, "hdwf"),
        (_IN, c_int, "cDQ"),
        (_IN, c_int, "cBitPerWord"),
        (_IN, POINTER(c_ubyte), "rgTX"),
        (_IN, c_int, "cTX"),
        (_IN, POINTER(c_ubyte), "rgRX"),
        (_IN, c_int, "cRX"),
    )

    _bindings.dwf_digital_spi_write_read16 = _patch(
        "FDwfDigitalSpiWriteRead16",
        (_IN, HDWF, "hdwf"),
        (_IN, c_int, "cDQ"),
        (_IN, c_int, "cBitPerWord"),
        (_IN, POINTER(c_ushort), "rgTX"),
        (_IN, c_int, "cTX"),
        (_IN, POINTER(c_ushort), "rgRX"),
        (_IN, c_int, "cRX"),
    )

    _bindings.dwf_digital_spi_write_read32 = _patch(
        "FDwfDigitalSpiWriteRead32",
        (_IN, HDWF, "hdwf"),
        (_IN, c_int, "cDQ"),
        (_IN, c_int, "cBitPerWord"),
        (_IN, POINTER(c_uint), "rgTX"),
        (_IN, c_int, "cTX"),
        (_IN, POINTER(c_uint), "rgRX"),
        (_IN, c_int, "cRX"),
    )

    logger.info("Applied dwfpy SPI read/write_read binding patches.")
