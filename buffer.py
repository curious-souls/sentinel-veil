"""
buffer.py - memory-only holding area with a timed wipe, plus a disk-write check.

HONEST LIMIT: Python may keep other copies of a string (interpreter, GC, swap).
This shows the idea. A real product would use locked memory (mlock), swap off
and encrypted memory. That is listed as future work.
"""
import os
import time


class RamBuffer:
    def __init__(self, ttl_seconds: float = 5.0):
        self.ttl = ttl_seconds
        self._data = bytearray()
        self._born = None

    def put(self, text: str):
        self._data = bytearray(text.encode("utf-8"))
        self._born = time.monotonic()

    @property
    def size(self) -> int:
        return len(self._data)

    def age(self) -> float:
        return 0.0 if self._born is None else time.monotonic() - self._born

    def remaining(self) -> float:
        return max(0.0, self.ttl - self.age())

    def wipe(self) -> dict:
        """Overwrite every byte with zero, then release. Returns proof."""
        n = len(self._data)
        for i in range(n):
            self._data[i] = 0
        all_zero = all(b == 0 for b in self._data)
        self._data = bytearray()
        self._born = None
        return {"bytes_overwritten": n, "all_zero_before_release": all_zero, "size_after": len(self._data)}


class DiskWatch:
    """Counts files in the project folder before and after a run."""

    IGNORE = ("__pycache__", ".git")

    def __init__(self, root: str):
        self.root = root
        self.before = self._snapshot()

    def _snapshot(self):
        snap = {}
        for folder, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in self.IGNORE and d != "results"]
            for f in files:
                p = os.path.join(folder, f)
                try:
                    st = os.stat(p)
                    snap[p] = (st.st_size, st.st_mtime_ns)
                except OSError:
                    pass
        return snap

    def new_or_changed(self) -> int:
        after = self._snapshot()
        return sum(1 for p, v in after.items() if self.before.get(p) != v)
