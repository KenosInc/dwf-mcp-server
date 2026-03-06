"""Tests for dwf-mcp-server tools."""

import asyncio
import importlib
import logging
import math
from unittest.mock import MagicMock, mock_open, patch

from fastmcp import FastMCP

import dwf_mcp_server.server as srv
import dwf_mcp_server.tools.analog as analog_mod
from dwf_mcp_server.diagnostics import check_environment
from dwf_mcp_server.tools.analog import analog_capture, generate_waveform, measure
from dwf_mcp_server.tools.devices import device_info, list_devices
from dwf_mcp_server.tools.digital import digital_capture
from dwf_mcp_server.tools.gpio import gpio_read, gpio_write
from dwf_mcp_server.tools.power import power_supply
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

    def test_enumerate_exception_returns_error_list(self) -> None:
        """Enumerate exception is caught and returned as a single-element error list."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.side_effect = RuntimeError("libdwf not found")

        with patch("dwf_mcp_server.tools.devices.dwf", dwf_mock):
            result = list_devices()

        assert isinstance(result, list)
        assert len(result) == 1
        assert "error" in result[0]
        assert "libdwf not found" in result[0]["error"]


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

    def test_enumerate_exception_returns_error(self) -> None:
        """Enumerate exception is caught and returned as error dict."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.side_effect = RuntimeError("libdwf not found")

        with patch("dwf_mcp_server.tools.devices.dwf", dwf_mock):
            result = device_info()

        assert "error" in result
        assert "libdwf not found" in result["error"]


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
        """All ten tools are registered on the server."""
        tools = asyncio.run(srv.mcp.list_tools())
        tool_names = {t.name for t in tools}
        expected = {
            "list_devices",
            "device_info",
            "analog_capture",
            "generate_waveform",
            "measure",
            "digital_capture",
            "gpio_read",
            "gpio_write",
            "power_supply",
            "spi_transfer",
        }
        assert expected.issubset(tool_names)


# ---------------------------------------------------------------------------
# power.power_supply
# ---------------------------------------------------------------------------


class TestPowerSupply:
    def _make_dwf_mock(self) -> MagicMock:
        """Create a dwf mock with analog_io support."""
        return MagicMock()

    def _get_aio(self, dwf_mock: MagicMock) -> MagicMock:
        """Get the analog_io mock from the device context."""
        return dwf_mock.Device.return_value.__enter__.return_value.analog_io

    def test_enable_sets_voltages_and_master(self) -> None:
        """Enabling sets both channel voltages, enables channels, and master."""
        dwf_mock = self._make_dwf_mock()
        aio = self._get_aio(dwf_mock)

        with patch("dwf_mcp_server.tools.power.dwf", dwf_mock):
            result = power_supply(positive_voltage=3.3, negative_voltage=-3.3, enabled=True)

        assert "error" not in result
        assert result["enabled"] is True
        assert result["positive_voltage"] == 3.3
        assert result["negative_voltage"] == -3.3
        aio.__getitem__.assert_any_call(0)
        aio.__getitem__.assert_any_call(1)
        assert aio.master_enable == True  # noqa: E712

    def test_disable_sets_master_false_and_channel_enables(self) -> None:
        """Disabling sets channel enables and master_enable to False."""
        dwf_mock = self._make_dwf_mock()
        aio = self._get_aio(dwf_mock)

        with patch("dwf_mcp_server.tools.power.dwf", dwf_mock):
            result = power_supply(enabled=False)

        assert "error" not in result
        assert result["enabled"] is False
        assert "positive_voltage" not in result
        assert "negative_voltage" not in result
        aio.__getitem__.assert_any_call(0)
        aio.__getitem__.assert_any_call(1)
        assert aio.master_enable == False  # noqa: E712

    def test_default_voltages(self) -> None:
        """Default voltages are 5.0 and -5.0."""
        dwf_mock = self._make_dwf_mock()

        with patch("dwf_mcp_server.tools.power.dwf", dwf_mock):
            result = power_supply()

        assert result["positive_voltage"] == 5.0
        assert result["negative_voltage"] == -5.0

    def test_positive_voltage_out_of_range_returns_error(self) -> None:
        """Positive voltage outside [0.5, 5.0] returns an error."""
        result = power_supply(positive_voltage=0.0)
        assert "error" in result
        assert "positive_voltage" in result["error"]

        result = power_supply(positive_voltage=6.0)
        assert "error" in result
        assert "positive_voltage" in result["error"]

    def test_negative_voltage_out_of_range_returns_error(self) -> None:
        """Negative voltage outside [-5.0, -0.5] returns an error."""
        result = power_supply(negative_voltage=0.0)
        assert "error" in result
        assert "negative_voltage" in result["error"]

        result = power_supply(negative_voltage=-6.0)
        assert "error" in result
        assert "negative_voltage" in result["error"]

        result = power_supply(negative_voltage=1.0)
        assert "error" in result
        assert "negative_voltage" in result["error"]

    def test_device_exception_returns_error(self) -> None:
        """Device-level exception is caught and returned as error dict."""
        dwf_mock = MagicMock()
        dwf_mock.Device.side_effect = RuntimeError("No device found")

        with patch("dwf_mcp_server.tools.power.dwf", dwf_mock):
            result = power_supply()

        assert "error" in result
        assert "No device found" in result["error"]


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
        spi_mock.setup.assert_called_once_with(
            pin_clock=1,
            pin_mosi=2,
            pin_miso=None,
            pin_select=0,
            frequency=1_000_000.0,
            mode=0,
            msb_first=True,
        )  # 0-based pins passed directly to dwfpy
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


# ---------------------------------------------------------------------------
# gpio.gpio_read
# ---------------------------------------------------------------------------


class TestGpioRead:
    def _make_dwf_mock(self, input_state: bool = True) -> MagicMock:
        """Create a dwf mock with digital I/O support for reading."""
        dwf_mock = MagicMock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        dio_mock = device_mock.digital_io
        dio_mock.__getitem__.return_value.input_state = input_state
        return dwf_mock

    def test_happy_path_high(self) -> None:
        """Reads a HIGH pin and returns pin number and value."""
        dwf_mock = self._make_dwf_mock(input_state=True)

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            result = gpio_read(pin=0)

        assert "error" not in result
        assert result["pin"] == 0
        assert result["value"] is True

    def test_happy_path_low(self) -> None:
        """Reads a LOW pin and returns pin number and value."""
        dwf_mock = self._make_dwf_mock(input_state=False)

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            result = gpio_read(pin=5)

        assert "error" not in result
        assert result["pin"] == 5
        assert result["value"] is False

    def test_pin_indexing(self) -> None:
        """Pin 3 (0-based) is passed directly to dwfpy as index 3."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        dio_mock = device_mock.digital_io

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            gpio_read(pin=3)

        dio_mock.__getitem__.assert_called_with(3)

    def test_auto_configures_as_input(self) -> None:
        """Pin is configured as input (enabled=False) before reading."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        dio_mock = device_mock.digital_io
        channel_mock = dio_mock.__getitem__.return_value

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            gpio_read(pin=0)

        channel_mock.setup.assert_called_once_with(enabled=False, configure=True)
        dio_mock.read_status.assert_called_once()

    def test_max_pin_succeeds(self) -> None:
        """Pin 15 (the maximum) succeeds and is passed directly to dwfpy."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        dio_mock = device_mock.digital_io

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            result = gpio_read(pin=15)

        assert "error" not in result
        assert result["pin"] == 15
        dio_mock.__getitem__.assert_called_with(15)

    def test_pin_below_range_returns_error(self) -> None:
        """Pin -1 returns an error (minimum is 0)."""
        result = gpio_read(pin=-1)
        assert "error" in result
        assert "out of range" in result["error"]

    def test_pin_above_range_returns_error(self) -> None:
        """Pin 16 returns an error (maximum is 15)."""
        result = gpio_read(pin=16)
        assert "error" in result
        assert "out of range" in result["error"]

    def test_device_exception_returns_error(self) -> None:
        """Device open exception is caught and returned as error dict."""
        dwf_mock = MagicMock()
        dwf_mock.Device.side_effect = RuntimeError("No device found")

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            result = gpio_read(pin=0)

        assert "error" in result
        assert "No device found" in result["error"]

    def test_device_index_forwarded(self) -> None:
        """Non-default device_index is forwarded to dwf.Device."""
        dwf_mock = self._make_dwf_mock()

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            gpio_read(pin=0, device_index=2)

        dwf_mock.Device.assert_called_once_with(device_id=2)


# ---------------------------------------------------------------------------
# gpio.gpio_write
# ---------------------------------------------------------------------------


class TestGpioWrite:
    def _make_dwf_mock(self) -> MagicMock:
        """Create a dwf mock with digital I/O support for writing."""
        dwf_mock = MagicMock()
        return dwf_mock

    def test_happy_path_set_high(self) -> None:
        """Sets a pin HIGH and returns pin number and value."""
        dwf_mock = self._make_dwf_mock()

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            result = gpio_write(pin=0, value=True)

        assert "error" not in result
        assert result["pin"] == 0
        assert result["value"] is True

    def test_happy_path_set_low(self) -> None:
        """Sets a pin LOW and returns pin number and value."""
        dwf_mock = self._make_dwf_mock()

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            result = gpio_write(pin=8, value=False)

        assert "error" not in result
        assert result["pin"] == 8
        assert result["value"] is False

    def test_pin_indexing(self) -> None:
        """Pin 5 (0-based) is passed directly to dwfpy as index 5."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        dio_mock = device_mock.digital_io

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            gpio_write(pin=5, value=True)

        dio_mock.__getitem__.assert_called_with(5)

    def test_configures_as_output_with_state(self) -> None:
        """Pin is configured as output (enabled=True) with the requested state."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        dio_mock = device_mock.digital_io
        channel_mock = dio_mock.__getitem__.return_value

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            gpio_write(pin=0, value=True)

        channel_mock.setup.assert_called_once_with(enabled=True, state=True, configure=True)

    def test_configures_as_output_with_state_low(self) -> None:
        """Pin is configured as output with state=False when value is False."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        dio_mock = device_mock.digital_io
        channel_mock = dio_mock.__getitem__.return_value

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            gpio_write(pin=0, value=False)

        channel_mock.setup.assert_called_once_with(enabled=True, state=False, configure=True)

    def test_pin_below_range_returns_error(self) -> None:
        """Pin -1 returns an error (minimum is 0)."""
        result = gpio_write(pin=-1, value=True)
        assert "error" in result
        assert "out of range" in result["error"]

    def test_pin_above_range_returns_error(self) -> None:
        """Pin 16 returns an error (maximum is 15)."""
        result = gpio_write(pin=16, value=True)
        assert "error" in result
        assert "out of range" in result["error"]

    def test_device_exception_returns_error(self) -> None:
        """Device open exception is caught and returned as error dict."""
        dwf_mock = MagicMock()
        dwf_mock.Device.side_effect = RuntimeError("No device found")

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            result = gpio_write(pin=0, value=True)

        assert "error" in result
        assert "No device found" in result["error"]

    def test_device_index_forwarded(self) -> None:
        """Non-default device_index is forwarded to dwf.Device."""
        dwf_mock = self._make_dwf_mock()

        with patch("dwf_mcp_server.tools.gpio.dwf", dwf_mock):
            gpio_write(pin=0, value=True, device_index=3)

        dwf_mock.Device.assert_called_once_with(device_id=3)


# ---------------------------------------------------------------------------
# analog.analog_capture
# ---------------------------------------------------------------------------


class TestAnalogCapture:
    def _make_dwf_mock(self, samples: list[float] | None = None) -> MagicMock:
        """Create a dwf mock with oscilloscope support."""
        if samples is None:
            samples = [0.1, 0.2, 0.3]
        dwf_mock = MagicMock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        scope_mock = device_mock.analog_input
        scope_mock.read_status.return_value = dwf_mock.Status.DONE
        scope_mock.__getitem__.return_value.get_data.return_value.tolist.return_value = samples
        return dwf_mock

    def test_happy_path(self) -> None:
        """End-to-end capture returns samples and metadata."""
        dwf_mock = self._make_dwf_mock([1.0, 2.0, 3.0])

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            result = analog_capture(channel=1, sample_rate=1000.0, duration=0.003)

        assert "error" not in result
        assert result["channel"] == 1
        assert result["sample_rate"] == 1000.0
        assert result["duration"] == 0.003
        assert result["sample_count"] == 3
        assert result["unit"] == "V"
        assert result["samples"] == [1.0, 2.0, 3.0]

    def test_asserts_correct_method_calls(self) -> None:
        """Verifies setup_acquisition and channel setup are called with correct args."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        scope_mock = device_mock.analog_input

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            analog_capture(channel=1, sample_rate=1_000_000.0, duration=0.001, voltage_range=5.0)

        scope_mock.__getitem__.assert_any_call(0)
        scope_mock.__getitem__.return_value.setup.assert_called_once_with(range=5.0, enabled=True)
        scope_mock.setup_acquisition.assert_called_once_with(
            sample_rate=1_000_000.0, buffer_size=1000, start=True
        )
        scope_mock.read_status.assert_called_with(read_data=True)

    def test_channel_indexing(self) -> None:
        """Channel 2 maps to 0-based index 1."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        scope_mock = device_mock.analog_input

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            result = analog_capture(channel=2)

        assert result["channel"] == 2
        scope_mock.__getitem__.assert_any_call(1)

    def test_timeout_returns_error(self) -> None:
        """Returns error when acquisition never completes."""
        dwf_mock = MagicMock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        scope_mock = device_mock.analog_input
        # read_status never returns DONE
        scope_mock.read_status.return_value = MagicMock()

        with (
            patch("dwf_mcp_server.tools.analog.dwf", dwf_mock),
            patch("dwf_mcp_server.tools.analog.time") as time_mock,
        ):
            # First call to monotonic() sets deadline, subsequent calls exceed it
            time_mock.monotonic.side_effect = [0.0, 100.0]

            result = analog_capture()

        assert "error" in result
        assert "timed out" in result["error"].lower()

    def test_device_index_forwarded(self) -> None:
        """Non-default device_index is forwarded to dwf.Device."""
        dwf_mock = self._make_dwf_mock()

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            analog_capture(device_index=2)

        dwf_mock.Device.assert_called_once_with(device_id=2)

    def test_device_exception_returns_error(self) -> None:
        """Device open exception is caught and returned as error dict."""
        dwf_mock = MagicMock()
        dwf_mock.Device.side_effect = RuntimeError("No device found")

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            result = analog_capture()

        assert "error" in result
        assert "No device found" in result["error"]


# ---------------------------------------------------------------------------
# analog.generate_waveform
# ---------------------------------------------------------------------------


class TestGenerateWaveform:
    def _make_dwf_mock(self) -> tuple[MagicMock, MagicMock]:
        """Create a dwf mock with AWG support. Returns (dwf_mock, ch_mock)."""
        dwf_mock = MagicMock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        ch_mock = device_mock.analog_output.__getitem__.return_value
        return dwf_mock, ch_mock

    def test_continuous_generation(self) -> None:
        """Continuous generation (duration=0) returns 'continuous' and no reset."""
        dwf_mock, ch_mock = self._make_dwf_mock()

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            result = generate_waveform(channel=1, waveform="sine", duration=0.0)

        assert "error" not in result
        assert result["waveform"] == "sine"
        assert result["duration"] == "continuous"
        ch_mock.reset.assert_not_called()

    def test_timed_generation(self) -> None:
        """Timed generation (duration>0) calls time.sleep and ch.reset."""
        dwf_mock, ch_mock = self._make_dwf_mock()

        with (
            patch("dwf_mcp_server.tools.analog.dwf", dwf_mock),
            patch("dwf_mcp_server.tools.analog.time") as time_mock,
        ):
            result = generate_waveform(channel=1, waveform="square", duration=0.5)

        assert "error" not in result
        assert result["duration"] == 0.5
        time_mock.sleep.assert_called_once_with(0.5)
        ch_mock.reset.assert_called_once()

    def test_asserts_correct_setup_call(self) -> None:
        """Verifies ch.setup is called with correct positional and keyword args."""
        dwf_mock, ch_mock = self._make_dwf_mock()

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            generate_waveform(
                channel=1,
                waveform="triangle",
                frequency=5000.0,
                amplitude=2.0,
                offset=0.5,
            )

        ch_mock.setup.assert_called_once_with(
            "triangle", frequency=5000.0, amplitude=2.0, offset=0.5, start=True
        )

    def test_channel_indexing(self) -> None:
        """Channel 2 maps to 0-based index 1."""
        dwf_mock, _ = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            result = generate_waveform(channel=2)

        assert result["channel"] == 2
        device_mock.analog_output.__getitem__.assert_called_with(1)

    def test_device_exception_returns_error(self) -> None:
        """Device open exception is caught and returned as error dict."""
        dwf_mock = MagicMock()
        dwf_mock.Device.side_effect = RuntimeError("No device found")

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            result = generate_waveform()

        assert "error" in result
        assert "No device found" in result["error"]


# ---------------------------------------------------------------------------
# analog.measure
# ---------------------------------------------------------------------------


class TestMeasure:
    def _make_dwf_mock(self, samples: list[float] | None = None) -> MagicMock:
        """Create a dwf mock with oscilloscope support for measurements."""
        if samples is None:
            samples = [1.0, 2.0, 3.0]
        dwf_mock = MagicMock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        scope_mock = device_mock.analog_input
        scope_mock.read_status.return_value = dwf_mock.Status.DONE
        scope_mock.__getitem__.return_value.get_data.return_value.tolist.return_value = samples
        return dwf_mock

    def test_happy_path(self) -> None:
        """End-to-end measure returns channel, measurement type, value, and unit."""
        dwf_mock = self._make_dwf_mock([1.0, 2.0, 3.0])

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            result = measure(channel=1, measurement="dc")

        assert "error" not in result
        assert result["channel"] == 1
        assert result["measurement"] == "dc"
        assert result["value"] == 2.0
        assert result["unit"] == "V"

    def test_rms_integration(self) -> None:
        """Measure with measurement='rms' flows through _compute_measurement correctly."""
        # mean([1,-1,1,-1]) = 0.0, but RMS = 1.0 — distinguishes dc from rms
        dwf_mock = self._make_dwf_mock([1.0, -1.0, 1.0, -1.0])

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            result = measure(channel=1, measurement="rms")

        assert "error" not in result
        assert result["measurement"] == "rms"
        assert math.isclose(result["value"], 1.0, rel_tol=1e-9)
        assert result["unit"] == "V"

    def test_setup_no_voltage_range(self) -> None:
        """Measure calls scope[ch].setup(enabled=True) without range argument."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        scope_mock = device_mock.analog_input

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            measure(channel=1)

        scope_mock.__getitem__.return_value.setup.assert_called_once_with(enabled=True)

    def test_setup_acquisition_called(self) -> None:
        """Verifies setup_acquisition is called with correct args."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        scope_mock = device_mock.analog_input

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            measure(sample_rate=1_000_000.0, duration=0.01)

        scope_mock.setup_acquisition.assert_called_once_with(
            sample_rate=1_000_000.0, buffer_size=10000, start=True
        )

    def test_timeout_returns_error(self) -> None:
        """Returns error when measurement never completes."""
        dwf_mock = MagicMock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        scope_mock = device_mock.analog_input
        scope_mock.read_status.return_value = MagicMock()

        with (
            patch("dwf_mcp_server.tools.analog.dwf", dwf_mock),
            patch("dwf_mcp_server.tools.analog.time") as time_mock,
        ):
            time_mock.monotonic.side_effect = [0.0, 100.0]

            result = measure()

        assert "error" in result
        assert "timed out" in result["error"].lower()

    def test_device_exception_returns_error(self) -> None:
        """Device open exception is caught and returned as error dict."""
        dwf_mock = MagicMock()
        dwf_mock.Device.side_effect = RuntimeError("No device found")

        with patch("dwf_mcp_server.tools.analog.dwf", dwf_mock):
            result = measure()

        assert "error" in result
        assert "No device found" in result["error"]


# ---------------------------------------------------------------------------
# digital.digital_capture
# ---------------------------------------------------------------------------


class TestDigitalCapture:
    def _make_dwf_mock(self, samples: list[int] | None = None) -> MagicMock:
        """Create a dwf mock with logic analyzer support."""
        if samples is None:
            samples = [0b1111, 0b0101, 0b1010]
        dwf_mock = MagicMock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        la_mock = device_mock.digital_input
        la_mock.read_status.return_value = dwf_mock.Status.DONE
        la_mock.get_data.return_value.tolist.return_value = samples
        return dwf_mock

    def test_happy_path_all_channels(self) -> None:
        """Capture with channels=None returns all 16 channels, no masking."""
        dwf_mock = self._make_dwf_mock([0xFF, 0x00, 0xAA])

        with patch("dwf_mcp_server.tools.digital.dwf", dwf_mock):
            result = digital_capture(channels=None, sample_rate=1000.0, duration=0.003)

        assert "error" not in result
        assert result["channels"] == list(range(16))
        assert result["sample_rate"] == 1000.0
        assert result["duration"] == 0.003
        assert result["sample_count"] == 3
        assert result["samples"] == [0xFF, 0x00, 0xAA]

    def test_channel_mask_filtering(self) -> None:
        """Capture with specific channels applies bitmask to samples."""
        # channels [0, 2] → mask = 0b101 = 5
        raw_samples = [0b1111, 0b0101, 0b1010]
        dwf_mock = self._make_dwf_mock(raw_samples)

        with patch("dwf_mcp_server.tools.digital.dwf", dwf_mock):
            result = digital_capture(channels=[0, 2])

        assert result["channels"] == [0, 2]
        # 0b1111 & 0b101 = 0b101 = 5
        # 0b0101 & 0b101 = 0b101 = 5
        # 0b1010 & 0b101 = 0b000 = 0
        assert result["samples"] == [5, 5, 0]

    def test_asserts_correct_method_calls(self) -> None:
        """Verifies setup_acquisition and read_status are called correctly."""
        dwf_mock = self._make_dwf_mock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        la_mock = device_mock.digital_input

        with patch("dwf_mcp_server.tools.digital.dwf", dwf_mock):
            digital_capture(sample_rate=2_000_000.0, duration=0.001)

        la_mock.setup_acquisition.assert_called_once_with(
            sample_rate=2_000_000.0, buffer_size=2000, start=True
        )
        la_mock.read_status.assert_called_with(read_data=True)

    def test_timeout_returns_error(self) -> None:
        """Returns error when capture never completes."""
        dwf_mock = MagicMock()
        device_mock = dwf_mock.Device.return_value.__enter__.return_value
        la_mock = device_mock.digital_input
        la_mock.read_status.return_value = MagicMock()

        with (
            patch("dwf_mcp_server.tools.digital.dwf", dwf_mock),
            patch("dwf_mcp_server.tools.digital.time") as time_mock,
        ):
            time_mock.monotonic.side_effect = [0.0, 100.0]

            result = digital_capture()

        assert "error" in result
        assert "timed out" in result["error"].lower()

    def test_device_exception_returns_error(self) -> None:
        """Device open exception is caught and returned as error dict."""
        dwf_mock = MagicMock()
        dwf_mock.Device.side_effect = RuntimeError("No device found")

        with patch("dwf_mcp_server.tools.digital.dwf", dwf_mock):
            result = digital_capture()

        assert "error" in result
        assert "No device found" in result["error"]


# ---------------------------------------------------------------------------
# diagnostics.check_environment
# ---------------------------------------------------------------------------

_DIAG = "dwf_mcp_server.diagnostics"


class TestCheckEnvironment:
    """Tests for startup environment diagnostics."""

    _CONF = "DigilentPath=/opt/digilent\nDigilentDataPath=/usr/share/digilent\n"

    def _patch_docker(self, is_docker: bool = True):  # noqa: FBT001,FBT002
        return patch(f"{_DIAG}._is_docker", return_value=is_docker)

    def test_skips_outside_docker(self) -> None:
        """Returns True immediately when not in Docker."""
        with self._patch_docker(False):
            assert check_environment() is True

    def test_all_checks_pass(self) -> None:
        """Returns True when all prerequisites are met."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = [MagicMock()]

        with (
            self._patch_docker(),
            patch(f"{_DIAG}.os.path.isfile", return_value=True),
            patch(f"{_DIAG}.os.path.isdir", return_value=True),
            patch(f"{_DIAG}.os.listdir", return_value=["firmware.hex"]),
            patch(f"{_DIAG}.open", mock_open(read_data=self._CONF)),
            patch(f"{_DIAG}.tempfile.NamedTemporaryFile"),
            patch(f"{_DIAG}.dwf", dwf_mock),
        ):
            assert check_environment() is True

    def test_missing_adept_conf(self, caplog: logging.LogCaptureFixture) -> None:
        """Returns False when /etc/digilent-adept.conf is missing."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = [MagicMock()]

        def fake_isfile(path: str) -> bool:
            return path != "/etc/digilent-adept.conf"

        with (
            self._patch_docker(),
            patch(f"{_DIAG}.os.path.isfile", side_effect=fake_isfile),
            patch(f"{_DIAG}.os.path.isdir", return_value=True),
            patch(f"{_DIAG}.os.listdir", return_value=["firmware.hex"]),
            patch(f"{_DIAG}.tempfile.NamedTemporaryFile"),
            patch(f"{_DIAG}.dwf", dwf_mock),
            caplog.at_level(logging.ERROR),
        ):
            assert check_environment() is False

        assert "not found" in caplog.text
        assert "digilent-adept.conf" in caplog.text

    def test_invalid_digilent_path(self, caplog: logging.LogCaptureFixture) -> None:
        """Returns False when DigilentPath points to nonexistent directory."""
        conf_content = "DigilentPath=/nonexistent\nDigilentDataPath=/usr/share/digilent\n"
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = [MagicMock()]

        def fake_isdir(path: str) -> bool:
            return path != "/nonexistent"

        with (
            self._patch_docker(),
            patch(f"{_DIAG}.os.path.isfile", return_value=True),
            patch(f"{_DIAG}.os.path.isdir", side_effect=fake_isdir),
            patch(f"{_DIAG}.os.listdir", return_value=["firmware.hex"]),
            patch(f"{_DIAG}.open", mock_open(read_data=conf_content)),
            patch(f"{_DIAG}.tempfile.NamedTemporaryFile"),
            patch(f"{_DIAG}.dwf", dwf_mock),
            caplog.at_level(logging.ERROR),
        ):
            assert check_environment() is False

        assert "DigilentPath" in caplog.text

    def test_no_firmware_dir(self, caplog: logging.LogCaptureFixture) -> None:
        """Returns False when firmware directory is missing."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = [MagicMock()]

        def fake_isdir(path: str) -> bool:
            return path != "/usr/share/digilent/waveforms/firmware"

        with (
            self._patch_docker(),
            patch(f"{_DIAG}.os.path.isfile", return_value=True),
            patch(f"{_DIAG}.os.path.isdir", side_effect=fake_isdir),
            patch(f"{_DIAG}.open", mock_open(read_data=self._CONF)),
            patch(f"{_DIAG}.tempfile.NamedTemporaryFile"),
            patch(f"{_DIAG}.dwf", dwf_mock),
            caplog.at_level(logging.ERROR),
        ):
            assert check_environment() is False

        assert "firmware" in caplog.text.lower()

    def test_empty_firmware_dir(self, caplog: logging.LogCaptureFixture) -> None:
        """Returns False when firmware directory has no .hex files."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = [MagicMock()]

        with (
            self._patch_docker(),
            patch(f"{_DIAG}.os.path.isfile", return_value=True),
            patch(f"{_DIAG}.os.path.isdir", return_value=True),
            patch(f"{_DIAG}.os.listdir", return_value=["readme.txt"]),
            patch(f"{_DIAG}.open", mock_open(read_data=self._CONF)),
            patch(f"{_DIAG}.tempfile.NamedTemporaryFile"),
            patch(f"{_DIAG}.dwf", dwf_mock),
            caplog.at_level(logging.ERROR),
        ):
            assert check_environment() is False

        assert ".hex" in caplog.text

    def test_tmp_not_writable(self, caplog: logging.LogCaptureFixture) -> None:
        """/tmp not writable causes failure."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = [MagicMock()]

        with (
            self._patch_docker(),
            patch(f"{_DIAG}.os.path.isfile", return_value=True),
            patch(f"{_DIAG}.os.path.isdir", return_value=True),
            patch(f"{_DIAG}.os.listdir", return_value=["firmware.hex"]),
            patch(f"{_DIAG}.open", mock_open(read_data=self._CONF)),
            patch(
                f"{_DIAG}.tempfile.NamedTemporaryFile",
                side_effect=OSError("read-only"),
            ),
            patch(f"{_DIAG}.dwf", dwf_mock),
            caplog.at_level(logging.ERROR),
        ):
            assert check_environment() is False

        assert "/tmp" in caplog.text

    def test_no_devices_warns_but_passes(self, caplog: logging.LogCaptureFixture) -> None:
        """No devices found logs warning but returns True."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.return_value = []

        with (
            self._patch_docker(),
            patch(f"{_DIAG}.os.path.isfile", return_value=True),
            patch(f"{_DIAG}.os.path.isdir", return_value=True),
            patch(f"{_DIAG}.os.listdir", return_value=["firmware.hex"]),
            patch(f"{_DIAG}.open", mock_open(read_data=self._CONF)),
            patch(f"{_DIAG}.tempfile.NamedTemporaryFile"),
            patch(f"{_DIAG}.dwf", dwf_mock),
            caplog.at_level(logging.WARNING),
        ):
            assert check_environment() is True

        assert "No Digilent WaveForms devices found" in caplog.text

    def test_dwf_enumerate_failure_warns_but_passes(
        self, caplog: logging.LogCaptureFixture
    ) -> None:
        """dwfpy enumerate failure logs warning but returns True."""
        dwf_mock = MagicMock()
        dwf_mock.Device.enumerate.side_effect = RuntimeError("libdwf not loaded")

        with (
            self._patch_docker(),
            patch(f"{_DIAG}.os.path.isfile", return_value=True),
            patch(f"{_DIAG}.os.path.isdir", return_value=True),
            patch(f"{_DIAG}.os.listdir", return_value=["firmware.hex"]),
            patch(f"{_DIAG}.open", mock_open(read_data=self._CONF)),
            patch(f"{_DIAG}.tempfile.NamedTemporaryFile"),
            patch(f"{_DIAG}.dwf", dwf_mock),
            caplog.at_level(logging.WARNING),
        ):
            assert check_environment() is True

        assert "libdwf" in caplog.text.lower()
