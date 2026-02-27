"""Tests for dwf-mcp-server tools."""

import asyncio
import importlib
import math
from unittest.mock import MagicMock, patch

from fastmcp import FastMCP

import dwf_mcp_server.server as srv
import dwf_mcp_server.tools.analog as analog_mod
from dwf_mcp_server.tools.devices import device_info, list_devices
from dwf_mcp_server.tools.protocols import spi_transfer


def _make_device_info(
    name: str = "Analog Discovery 2",
    serial: str = "SN12345",
    is_open: bool = False,
) -> MagicMock:
    info = MagicMock()
    info.name = name
    info.serial_number = serial
    info.is_open = is_open
    return info


# ---------------------------------------------------------------------------
# devices.list_devices
# ---------------------------------------------------------------------------


class TestListDevices:
    def test_returns_device_list(self) -> None:
        """Returns a list of device dicts when dwfpy is available."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = [_make_device_info()]

        with patch("dwf_mcp_server.tools.devices.dwf", dwf_mock):
            result = list_devices()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["index"] == 0
        assert result[0]["name"] == "Analog Discovery 2"
        assert result[0]["serial"] == "SN12345"
        assert result[0]["is_open"] is False

    def test_returns_empty_list_when_no_devices(self) -> None:
        """Returns an empty list when no devices are connected."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = []

        with patch("dwf_mcp_server.tools.devices.dwf", dwf_mock):
            result = list_devices()

        assert result == []


# ---------------------------------------------------------------------------
# devices.device_info
# ---------------------------------------------------------------------------


class TestDeviceInfo:
    def test_returns_device_info(self) -> None:
        """Returns info dict for valid device index."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = [_make_device_info()]

        with patch("dwf_mcp_server.tools.devices.dwf", dwf_mock):
            result = device_info(device_index=0)

        assert result["index"] == 0
        assert result["name"] == "Analog Discovery 2"
        assert "error" not in result

    def test_returns_error_for_out_of_range_index(self) -> None:
        """Returns an error when device_index exceeds available devices."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = [_make_device_info()]

        with patch("dwf_mcp_server.tools.devices.dwf", dwf_mock):
            result = device_info(device_index=5)

        assert "error" in result
        assert "out of range" in result["error"]

    def test_returns_error_when_no_devices(self) -> None:
        """Returns an error when no devices are found."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = []

        with patch("dwf_mcp_server.tools.devices.dwf", dwf_mock):
            result = device_info()

        assert "error" in result


# ---------------------------------------------------------------------------
# analog._compute_measurement
# ---------------------------------------------------------------------------


class TestComputeMeasurement:
    def setup_method(self) -> None:
        importlib.reload(analog_mod)
        self.compute = analog_mod._compute_measurement

    def test_dc_measurement(self) -> None:
        samples = [1.0, 2.0, 3.0]
        value, unit = self.compute(samples, "dc", 1_000_000.0)
        assert value == 2.0
        assert unit == "V"

    def test_rms_measurement(self) -> None:
        samples = [1.0, -1.0, 1.0, -1.0]
        value, unit = self.compute(samples, "rms", 1_000_000.0)
        assert math.isclose(value, 1.0, rel_tol=1e-9)
        assert unit == "V"

    def test_peak_to_peak_measurement(self) -> None:
        samples = [-2.0, 0.0, 2.0]
        value, unit = self.compute(samples, "peak_to_peak", 1_000_000.0)
        assert value == 4.0
        assert unit == "V"

    def test_frequency_measurement(self) -> None:
        # 1 kHz sine wave at 1 MHz sample rate → 1000 samples/period
        sample_rate = 1_000_000.0
        n = 10_000
        samples = [math.sin(2 * math.pi * 1000 * i / sample_rate) for i in range(n)]
        value, unit = self.compute(samples, "frequency", sample_rate)
        assert math.isclose(value, 1000.0, rel_tol=0.02)
        assert unit == "Hz"

    def test_frequency_no_crossings_returns_zero(self) -> None:
        samples = [1.0, 1.5, 2.0]  # all positive, no zero crossings
        value, unit = self.compute(samples, "frequency", 1_000_000.0)
        assert value == 0.0
        assert unit == "Hz"

    def test_period_measurement(self) -> None:
        sample_rate = 1_000_000.0
        n = 10_000
        samples = [math.sin(2 * math.pi * 1000 * i / sample_rate) for i in range(n)]
        value, unit = self.compute(samples, "period", sample_rate)
        assert math.isclose(value, 0.001, rel_tol=0.02)
        assert unit == "s"


# ---------------------------------------------------------------------------
# server: FastMCP instance is created and tools are registered
# ---------------------------------------------------------------------------


class TestServerRegistration:
    def test_mcp_instance_created(self) -> None:
        """The module-level mcp instance is a FastMCP object."""
        assert isinstance(srv.mcp, FastMCP)

    def test_tools_registered(self) -> None:
        """All seven tools are registered on the server."""
        tools = asyncio.run(srv.mcp.list_tools())
        tool_names = {t.name for t in tools}
        expected = {
            "list_devices",
            "device_info",
            "analog_capture",
            "generate_waveform",
            "measure",
            "digital_capture",
            "spi_transfer",
        }
        assert expected.issubset(tool_names)


# ---------------------------------------------------------------------------
# protocols.spi_transfer
# ---------------------------------------------------------------------------


class TestSpiTransfer:
    def _make_dwf_mock(self) -> MagicMock:
        """Create a dwf mock with SPI protocol support."""
        dwf_mock = MagicMock()
        spi_mock = dwf_mock.Device.return_value.__enter__.return_value.protocols.spi
        spi_mock.write_read.return_value = b"\xaa\xbb\xcc"
        return dwf_mock

    def test_write_only(self) -> None:
        """Write-only transfer (no MISO) returns mosi hex and null miso."""
        dwf_mock = self._make_dwf_mock()
        spi_mock = dwf_mock.Device.return_value.__enter__.return_value.protocols.spi

        with patch("dwf_mcp_server.tools.protocols.dwf", dwf_mock):
            result = spi_transfer(clock_pin=1, mosi_pin=2, cs_pin=0, mosi_data="180001")

        assert result["mosi"] == "180001"
        assert result["miso"] is None
        assert result["bits_transferred"] == 24
        spi_mock.setup.assert_called_once()
        spi_mock.write_one.assert_called_once_with(0x180001, bits_per_word=24)
        spi_mock.select.assert_any_call("low")
        spi_mock.select.assert_any_call("high")

    def test_write_read(self) -> None:
        """Full-duplex transfer (with MISO) returns both mosi and miso hex."""
        dwf_mock = self._make_dwf_mock()

        with patch("dwf_mcp_server.tools.protocols.dwf", dwf_mock):
            result = spi_transfer(
                clock_pin=1,
                mosi_pin=2,
                cs_pin=0,
                mosi_data="180001",
                miso_pin=3,
            )

        assert result["mosi"] == "180001"
        assert result["miso"] == "aabbcc"
        assert result["bits_transferred"] == 24

    def test_invalid_hex_returns_error(self) -> None:
        """Invalid hex string returns an error without opening the device."""
        result = spi_transfer(clock_pin=1, mosi_pin=2, cs_pin=0, mosi_data="ZZZZ")
        assert "error" in result
        assert "Invalid hex" in result["error"]

    def test_empty_hex_returns_error(self) -> None:
        """Empty hex string returns an error."""
        result = spi_transfer(clock_pin=1, mosi_pin=2, cs_pin=0, mosi_data="")
        assert "error" in result
        assert "empty" in result["error"]

    def test_invalid_mode_returns_error(self) -> None:
        """SPI mode outside 0-3 returns an error."""
        result = spi_transfer(clock_pin=1, mosi_pin=2, cs_pin=0, mosi_data="ff", mode=5)
        assert "error" in result
        assert "mode" in result["error"].lower()

    def test_device_exception_returns_error(self) -> None:
        """Device-level exception is caught and returned as error dict."""
        dwf_mock = MagicMock()
        dwf_mock.Device.side_effect = RuntimeError("No device found")

        with patch("dwf_mcp_server.tools.protocols.dwf", dwf_mock):
            result = spi_transfer(clock_pin=1, mosi_pin=2, cs_pin=0, mosi_data="ff")

        assert "error" in result
        assert "No device found" in result["error"]
