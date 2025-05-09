"""Acquisition thread wrapping BrainFlow board streaming."""

import threading
import time
import numpy as np
from collections import deque
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from config import Config


class RingBuffer:
    """Lock‑free ring buffer for real‑time EEG samples (n_chan × n_samples)."""

    def __init__(self, max_len: int = 12 * Config.SAMPLE_RATE):
        self.max_len = max_len
        self.buffer = deque(maxlen=max_len)
        self.lock = threading.Lock()

    def push(self, samples: np.ndarray):
        with self.lock:
            self.buffer.extend(samples.T)  # store column‑wise rows = time

    def get(self, n: int) -> np.ndarray:
        with self.lock:
            if len(self.buffer) < n:
                return np.empty((0, 0))
            # Convert list of 1D arrays -> 2D (n_chan, n)
            data = list(self.buffer)[-n:]
        return np.stack(data).T  # shape (n_chan, n)


class AcquisitionThread(threading.Thread):
    """Continuously pulls data from the board and pushes to RingBuffer."""

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
                    data = self.board.get_current_board_data(
                        int(Config.SAMPLE_RATE / 2)
                    )
                    self.ring.push(
                        data[self.eeg_ch, :]      # ➋ EEG-only slice
                    )
                    time.sleep(0.01)
            finally:
                self.board.stop_stream()
                self.board.release_session()
                
    def stop(self):
        self._stop.set()
