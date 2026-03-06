"""Digital protocol tools (SPI, I2C, UART) for Digilent WaveForms."""

import dwfpy as dwf
from fastmcp import FastMCP


def spi_transfer(
    clock_pin: int,
    mosi_pin: int,
    cs_pin: int,
    mosi_data: str,
    clock_frequency: float = 1_000_000.0,
    mode: int = 0,
    miso_pin: int | None = None,
    bits_per_word: int = 8,
    device_index: int = 0,
) -> dict:
    """Send and optionally receive data over SPI using the digital protocol interface.

    Args:
        clock_pin: DIO pin number for SPI clock (SCLK), 0-based (0-15).
        mosi_pin: DIO pin number for Master-Out Slave-In (MOSI / DIN), 0-based (0-15).
        cs_pin: DIO pin number for chip-select (active low), 0-based (0-15).
        mosi_data: Hex-encoded bytes to transmit, e.g. "180001" for 3 bytes.
        clock_frequency: SPI clock frequency in Hz (default: 1 MHz).
        mode: SPI mode 0-3 defining clock polarity/phase (default: 0).
        miso_pin: DIO pin number for Master-In Slave-Out (MISO / DOUT), 0-based (0-15).
            If None, a write-only transfer is performed.
        bits_per_word: Bits per SPI word, 1-32 (default: 8).
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with 'mosi' (hex string sent), 'miso' (hex string received or null),
        and 'bits_transferred'.
    """
    try:
        tx_bytes = bytes.fromhex(mosi_data)
    except ValueError:
        return {"error": f"Invalid hex string for mosi_data: {mosi_data!r}"}

    if not tx_bytes:
        return {"error": "mosi_data must not be empty."}

    if mode not in (0, 1, 2, 3):
        return {"error": f"Invalid SPI mode: {mode}. Must be 0, 1, 2, or 3."}

    try:
        with dwf.Device(device_id=device_index) as device:
            spi = device.protocols.spi
            spi.setup(
                pin_clock=clock_pin,
                pin_mosi=mosi_pin,
                pin_miso=miso_pin,
                pin_select=cs_pin,
                frequency=clock_frequency,
                mode=mode,
                msb_first=True,
            )

            total_bits = len(tx_bytes) * 8
            spi.select("low")
            try:
                if miso_pin is not None:
                    if total_bits <= 32:
                        tx_int = int.from_bytes(tx_bytes, byteorder="big")
                        rx_int = spi.write_read(
                            tx_bytes,
                            words_to_receive=len(tx_bytes),
                            bits_per_word=bits_per_word,
                        )
                        miso_hex = bytes(rx_int).hex()
                    else:
                        rx_bytes = spi.write_read(
                            tx_bytes,
                            words_to_receive=len(tx_bytes),
                            bits_per_word=bits_per_word,
                        )
                        miso_hex = bytes(rx_bytes).hex()
                else:
                    if total_bits <= 32:
                        tx_int = int.from_bytes(tx_bytes, byteorder="big")
                        spi.write_one(tx_int, bits_per_word=total_bits)
                    else:
                        spi.write(tx_bytes, bits_per_word=bits_per_word)
                    miso_hex = None
            finally:
                spi.select("high")

        return {
            "mosi": mosi_data,
            "miso": miso_hex,
            "bits_transferred": total_bits,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def register(mcp: FastMCP) -> None:
    """Register protocol tools with the MCP server."""
    mcp.tool(spi_transfer)
