"""Device session manager for persistent device connections."""

import logging
import threading

import dwfpy as dwf

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 300.0  # 5 minutes


class DeviceManager:
    """Manages persistent device connections with idle timeout.

    Devices are opened on first acquire() and kept open across tool calls.
    An idle timer auto-closes the device after a configurable timeout.
    Thread-safe via threading.Lock (FastMCP runs sync tools in a thread pool).
    """

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._devices: dict[int, dwf.Device] = {}
        self._timers: dict[int, threading.Timer] = {}
        self._lock = threading.Lock()
        self._timeout = timeout

    def acquire(self, device_index: int = 0) -> dwf.Device:
        """Return an open device, opening a new one if needed."""
        with self._lock:
            self._cancel_timer(device_index)

            if device_index in self._devices:
                self._start_timer(device_index)
                return self._devices[device_index]

            device = dwf.Device(device_id=device_index)
            device.open()
            self._devices[device_index] = device
            self._start_timer(device_index)
            return device

    def release(self, device_index: int = 0) -> bool:
        """Close a device session. Returns True if a device was closed."""
        with self._lock:
            return self._release_locked(device_index)

    def release_all(self) -> None:
        """Close all open device sessions (for server shutdown)."""
        with self._lock:
            for idx in list(self._devices):
                self._release_locked(idx)

    def is_open(self, device_index: int = 0) -> bool:
        """Check whether a device session is currently open."""
        with self._lock:
            return device_index in self._devices

    def _release_locked(self, device_index: int) -> bool:
        """Close a device (must be called with lock held)."""
        self._cancel_timer(device_index)
        device = self._devices.pop(device_index, None)
        if device is None:
            return False
        try:
            device.close()
        except Exception:  # noqa: BLE001
            logger.warning("Error closing device %d", device_index, exc_info=True)
        return True

    def _start_timer(self, device_index: int) -> None:
        """Start (or restart) the idle timeout timer (must be called with lock held)."""
        timer = threading.Timer(self._timeout, self._on_timeout, args=(device_index,))
        timer.daemon = True
        timer.start()
        self._timers[device_index] = timer

    def _cancel_timer(self, device_index: int) -> None:
        """Cancel an existing idle timer if any (must be called with lock held)."""
        timer = self._timers.pop(device_index, None)
        if timer is not None:
            timer.cancel()

    def _on_timeout(self, device_index: int) -> None:
        """Called when the idle timer fires."""
        logger.info("Idle timeout reached for device %d, closing session.", device_index)
        self.release(device_index)


_manager = DeviceManager()


def get_manager() -> DeviceManager:
    """Return the module-level DeviceManager singleton."""
    return _manager
