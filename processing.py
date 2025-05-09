"""Periodic worker that converts raw EEG into band power matrix."""

import threading, time, numpy as np
from brainflow.data_filter import DataFilter, WindowOperations
from config import Config
from collections import deque

class PowerMatrix:
    """Thread‑safe container for latest z‑scored power values."""

    def __init__(self):
        self.mat = np.zeros((8, len(Config.BANDS)), dtype=np.float32)
        self.lock = threading.Lock()

    def update(self, new_mat: np.ndarray):
        with self.lock:
            self.mat[:] = new_mat

    def fetch(self) -> np.ndarray:
        with self.lock:
            return self.mat.copy()


class ProcessingThread(threading.Thread):
    """Runs every Config.PROCESS_INTERVAL to compute band powers."""

    def __init__(self, ring_buffer, power_matrix: PowerMatrix):
        super().__init__(daemon=True)
        self.ring = ring_buffer
        self.pm = power_matrix
        self._stop = threading.Event()
        self._baseline_mu = None
        self._baseline_sigma = None

    def stop(self):
        self._stop.set()

    def calibrate(self):
        """Collect baseline for CALIBRATION_SEC seconds (eyes open)."""
        required = Config.CALIBRATION_SEC * Config.SAMPLE_RATE
        print(f"Calibration: keep eyes OPEN for {Config.CALIBRATION_SEC} s …")
        while True:
            chunk = self.ring.get(required)
            if chunk.shape[1] >= required:
                break
            time.sleep(0.1)

        powers = self._bandpowers(chunk)
        self._baseline_mu = powers.mean(axis=0, keepdims=True)   # (1, 5)
        self._baseline_sigma = powers.std(axis=0, ddof=1, keepdims=True) + 1e-6
        print("Calibration done.")

    def run(self):
        if self._baseline_mu is None:
            self.calibrate()

        samples_needed = Config.SAMPLE_RATE  
        while not self._stop.is_set():
            chunk = self.ring.get(samples_needed)
            if chunk.size:
                powers = self._bandpowers(chunk)

                # z‑score
                z = (powers - self._baseline_mu) / self._baseline_sigma
                z = np.clip(z, 0, 4) / 4.0  # 0‑1
                self.pm.update(z)
            time.sleep(Config.PROCESS_INTERVAL / 2)

    def _bandpowers(self, data: np.ndarray) -> np.ndarray:
        """
        Return band powers δ–γ for each channel as (n_chan, 5) float32.
        BrainFlow needs a C-contiguous row-major float64 matrix.
        """
        data = np.ascontiguousarray(data, dtype=np.float64)

        n_channels, _ = data.shape
        powers = np.zeros((n_channels, 5), dtype=np.float32)

        for ch in range(n_channels):
            band_avg, _ = DataFilter.get_avg_band_powers(
                data, [ch], Config.SAMPLE_RATE, False)
            powers[ch] = band_avg          # δ θ α β γ

        return powers                      # shape (8, 5)


