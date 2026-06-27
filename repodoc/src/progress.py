"""Progress tracking with ETA for long-running pipeline phases.

``ProgressTracker`` is a thread-/async-safe counter that logs a progress line
periodically (every ``log_every`` items or ``log_interval_seconds`` seconds,
whichever comes first, with an anti-burst floor) and a final summary on
``finish()``. The ETA is derived from the observed throughput, which stays
reliable on single-inference setups where work is effectively serialized.
"""

import logging
import threading
import time
from typing import Optional

_logger = logging.getLogger("repodoc.progress")


def _fmt_duration(seconds: float) -> str:
    s = int(max(0.0, seconds))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


class ProgressTracker:
    """Count completed units and periodically log progress with an ETA.

    Args:
        total: Total number of units to complete.
        label: Prefix used in log lines (e.g. "Phase 3").
        log_every: Emit after at least this many new completions (count trigger).
            Defaults to an adaptive ~total/100, clamped to [25, 200].
        log_interval_seconds: Emit after at least this many seconds (time trigger).
        min_interval_seconds: Hard floor between emits to avoid bursts.
        logger_: Logger to emit on; defaults to the ``repodoc.progress`` logger.
    """

    def __init__(
        self,
        total: int,
        label: str = "Progress",
        log_every: Optional[int] = None,
        log_interval_seconds: float = 30.0,
        min_interval_seconds: float = 3.0,
        logger_: Optional[logging.Logger] = None,
    ) -> None:
        self.total = max(0, int(total))
        self.label = label
        if log_every is None:
            log_every = max(25, min(200, self.total // 100 if self.total else 25))
        self.log_every = max(1, int(log_every))
        self.log_interval = max(1.0, float(log_interval_seconds))
        self.min_interval = max(0.5, float(min_interval_seconds))
        self._logger = logger_ or _logger

        self._completed = 0
        self._last_label = ""
        self._lock = threading.Lock()
        self._start = time.time()
        self._last_emit = self._start
        self._last_emit_count = 0

        if self.total > 0:
            self._logger.info("%s: 0/%d (0%%) | starting...", self.label, self.total)

    def tick(self, item: str = "") -> None:
        """Record one completed unit; emit a progress line if a trigger fires."""
        with self._lock:
            self._completed += 1
            if item:
                self._last_label = item
            completed = self._completed
            now = time.time()
            count_trigger = completed - self._last_emit_count >= self.log_every
            time_trigger = now - self._last_emit >= self.log_interval
            is_final = completed >= self.total
            if not (count_trigger or time_trigger or is_final):
                return
            # Anti-burst: never emit more than once per min_interval (final excepted).
            if not is_final and (now - self._last_emit) < self.min_interval:
                return
            self._last_emit = now
            self._last_emit_count = completed
        self._emit(completed)

    def _emit(self, completed: int) -> None:
        elapsed = time.time() - self._start
        pct = (completed / self.total * 100) if self.total else 0.0
        remaining = self.total - completed
        if completed > 0 and elapsed > 0 and remaining > 0:
            rate = completed / elapsed
            eta = remaining / rate
            eta_str = f"~{_fmt_duration(eta)}"
        elif remaining <= 0:
            eta_str = "done"
        else:
            eta_str = "?"
        last = f" | last: {self._last_label}" if self._last_label else ""
        self._logger.info(
            "%s: %d/%d (%.0f%%) | elapsed %s | ETA %s%s",
            self.label,
            completed,
            self.total,
            pct,
            _fmt_duration(elapsed),
            eta_str,
            last,
        )

    def finish(self) -> None:
        """Log a final summary line."""
        with self._lock:
            completed = self._completed
        elapsed = time.time() - self._start
        self._logger.info(
            "%s: done %d/%d | elapsed %s",
            self.label,
            completed,
            self.total,
            _fmt_duration(elapsed),
        )

    @property
    def completed(self) -> int:
        with self._lock:
            return self._completed
