"""Entry point: wires acquisition, processing and audio output."""

import argparse, sys, time
import numpy as np
import sounddevice as sd

from config import Config
from acquire import RingBuffer, AcquisitionThread
from processing import PowerMatrix, ProcessingThread
from synth import Sonifier


def pick_device(name_substr: str | None, host: str):
    hostapis = sd.query_hostapis()
    host_id = next((idx for idx, h in enumerate(hostapis) if host.lower() in h['name'].lower()), None)
    if host_id is None:
        print(f"Host '{host}' not found, falling back to default")
        return None
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if dev['hostapi'] == host_id and (name_substr is None or name_substr.lower() in dev['name'].lower()):
            return idx
    print(f"No device matching '{name_substr}' on host '{host}' — using default")
    return None


def main():
    parser = argparse.ArgumentParser(description="Real‑time EEG → Audio sonification")
    parser.add_argument("--serial", default=Config.SERIAL_PORT)
    args = parser.parse_args()

    # Overwrite config serial if given
    if args.serial:
        Config.SERIAL_PORT = args.serial

    ring = RingBuffer()
    power_mat = PowerMatrix()
    acq = AcquisitionThread(ring)
    proc = ProcessingThread(ring, power_mat)
    synth = Sonifier()

    print("Starting acquisition...")
    acq.start()
    proc.start()

    # Pick audio output
    device_idx = pick_device(Config.OUTPUT_DEVICE, Config.AUDIO_HOST)
    print(f"Using audio device: {device_idx if device_idx is not None else 'default'}")

    def callback(outdata, frames, timeinfo, status):
        z = power_mat.fetch()  # shape (8, 5)
        if z.size == 0:
            outdata[:] = np.zeros_like(outdata)
            return
        audio = synth(z, frames)
        outdata[:] = audio

    with sd.OutputStream(
        samplerate=Config.FS_AUDIO,
        blocksize=Config.BLOCKSIZE,
        channels=2,
        dtype='float32',
        callback=callback,
        device=device_idx,
        latency='low',
    ):
        print("Streaming audio…  Press Ctrl‑C to quit.")
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("Stopping…")
        finally:
            proc.stop()
            acq.stop()
            proc.join()
            acq.join()


if __name__ == "__main__":
    main()
