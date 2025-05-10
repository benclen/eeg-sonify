"""Acquisition threads: BrainFlow live stream **or** CSV playback."""

import csv
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams

from config import Config


# ────────────────────────── Shared infrastructure ────────────────────────── #

class RingBuffer:
    """Lock-free ring buffer for real-time EEG samples (n_chan × n_samples)."""

    def __init__(self, max_len: int = 12 * Config.SAMPLE_RATE):
        self.max_len = max_len
        self.buffer = deque(maxlen=max_len)
        self.lock = threading.Lock()

    def push(self, samples: np.ndarray):
        """
        `samples` shape: (n_chan, n_samples)  **column-major time axis**
        """
        with self.lock:
            self.buffer.extend(samples.T)  # store rows=time for cheap append

    def get(self, n: int) -> np.ndarray:
        """
        Return last *n* samples as (n_chan, n) – empty array if insufficient.
        """
        with self.lock:
            if len(self.buffer) < n:
                return np.empty((0, 0))
            data = list(self.buffer)[-n:]
        return np.stack(data).T


# ───────────────────────────────── Live board ─────────────────────────────── #

class AcquisitionThread(threading.Thread):
    """
    Pulls data from Cyton (BrainFlow) and pushes EEG channels to a RingBuffer.
    """

    def __init__(self, ring: RingBuffer):
        super().__init__(daemon=True)
        self.ring = ring
        self._stop = threading.Event()

        params = BrainFlowInputParams()
        params.serial_port = Config.SERIAL_PORT
        self.board = BoardShim(Config.BOARD_ID, params)
        self.eeg_ch = BoardShim.get_eeg_channels(Config.BOARD_ID)

    def run(self):
        self.board.prepare_session()
        self.board.start_stream(45000, "file://eeg_stream.csv:w")
        try:
            while not self._stop.is_set():
                data = self.board.get_current_board_data(int(Config.SAMPLE_RATE // 2))
                self.ring.push(data[self.eeg_ch, :])
                time.sleep(0.01)
        finally:
            self.board.stop_stream()
            self.board.release_session()

    def stop(self):
        self._stop.set()


# ───────────────────────────── CSV playback ───────────────────────────────── #

class FileAcquisitionThread(threading.Thread):
    """
    Replays an OpenBCI CSV as if it were coming from the board in real time.

    Each loop pushes `chunk_size` samples to the RingBuffer, then sleeps
    `chunk_size / sample_rate` so Processing + Synth run unmodified.
    """

    def __init__(
        self,
        ring: RingBuffer,
        filepath: str | Path,
        loop: bool = False,
        chunk_size: int | None = None,
        realtime: bool = True,
    ):
        super().__init__(daemon=True)
        self.ring = ring
        self.filepath = Path(filepath)
        self.loop = loop
        self.chunk_size = chunk_size or Config.SAMPLE_RATE // 2  # 125 @ 250 Hz
        self.realtime = realtime
        self._stop = threading.Event()

    # ── internal helpers ──────────────────────────────────────────────────── #

    def _read_header(self, reader):
        """
        Skip `%` comments, return header row list; locate EXG Channel columns.
        """
        for row in reader:
            if row and row[0].startswith("%"):
                continue
            header = row
            break
        eeg_cols = [
            idx for idx, col in enumerate(header)
            if col.strip().startswith("EXG Channel")
        ]
        if len(eeg_cols) < 8:
            raise ValueError("Expected ≥8 EXG Channel columns in CSV header")
        return eeg_cols

    def _stream_once(self):
        with self.filepath.open(newline="") as f:
            reader = csv.reader(f)
            eeg_cols = self._read_header(reader)

            buf = []  # collects rows until chunk_size reached
            for row in reader:
                if self._stop.is_set():
                    break
                if not row or row[0].startswith("%"):
                    continue  # skip stray comments in body
                try:
                    buf.append([float(row[i]) for i in eeg_cols[:8]])
                except ValueError:
                    continue  # skip malformed rows
                if len(buf) >= self.chunk_size:
                    self._flush(buf)
                    buf = []
            # final partial chunk
            if buf and not self._stop.is_set():
                self._flush(buf)

    def _flush(self, rows: list[list[float]]):
        self.ring.push(np.asarray(rows, dtype=np.float32).T)
        if self.realtime:
            time.sleep(len(rows) / Config.SAMPLE_RATE)

    # ── public thread interface ───────────────────────────────────────────── #

    def run(self):
        while not self._stop.is_set():
            self._stream_once()
            if not self.loop:
                break

    def stop(self):
        self._stop.set()
