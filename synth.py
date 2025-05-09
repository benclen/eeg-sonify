"""Realtime additive synthesiser mapping band power to pitched sines."""

import numpy as np
from config import Config


def midi_to_hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


class Sonifier:
    def __init__(self, fs: int = Config.FS_AUDIO):
        self.fs = fs
        self.phase = np.zeros((8, len(Config.BANDS)), dtype=np.float64)

        # Precompute channel‑degree offsets in semitones
        self.scale_degrees = np.array(Config.CHANNEL_DEGREES, dtype=np.float64)

        # Base MIDI notes per band in order of Config.BANDS
        self.base_midi = np.array([Config.BASE_MIDI[b] for b in Config.BANDS.keys()],
                                  dtype=np.float64)

    def __call__(self, z_power_mat: np.ndarray, n_samples: int) -> np.ndarray:
        """Generate n_samples of stereo audio.

        z_power_mat shape: (8 channels, 5 bands) values 0–1.
        Returns float32 array shape (n_samples, 2)
        """
        t = np.arange(n_samples, dtype=np.float64) / self.fs

        # Compute frequencies matrix chan×band
        midi = self.base_midi + self.scale_degrees[:, None]
        freqs = midi_to_hz(midi)

        # ADSR: amplitude directly equals z_power (soft saturate later)
        amps = z_power_mat

        # Vectorised phase accumulation
        phases = (self.phase + 2 * np.pi * freqs * t[:, None, None])
        samples = np.sin(phases) * amps  # broadcast t over axes

        # Sum over chan+band
        mono = samples.sum(axis=(1, 2))

        # Simple limiter
        mono = np.tanh(mono * 0.3)

        # Stereo pan by channel index (left 0‑3, right 4‑7)
        stereo = np.zeros((n_samples, 2), dtype=np.float32)
        left_mask = np.arange(8) < 4
        right_mask = ~left_mask
        left = samples[:, left_mask].sum(axis=(1, 2))
        right = samples[:, right_mask].sum(axis=(1, 2))
        stereo[:, 0] = np.tanh(left * 0.3)
        stereo[:, 1] = np.tanh(right * 0.3)

        # Update phase memory
        self.phase = (self.phase + 2 * np.pi * freqs * n_samples / self.fs) % (2 * np.pi)

        return stereo
