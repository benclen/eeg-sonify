"""Entry point: wires acquisition, processing and audio output."""

import argparse, sys, time
import numpy as np
import sounddevice as sd

from config import Config
from acquire import (
    RingBuffer,
    AcquisitionThread,      # live
    FileAcquisitionThread,  # file
    )
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
    parser = argparse.ArgumentParser(description="EEG → Audio sonification")
    parser.add_argument("--mode", choices=("live", "file"), default="live",
                        help="live = Cyton via BrainFlow (default); "
                             "file = replay OpenBCI CSV")
    parser.add_argument("--serial", default=Config.SERIAL_PORT,
                        help="COM port for Cyton when --mode live")
    parser.add_argument("--input", help="CSV file path when --mode file")
    parser.add_argument("--loop", action="store_true",
                        help="Loop the CSV endlessly")
    args = parser.parse_args()

    # ── choose acquisition source ────────────────────────────────────────── #
    ring = RingBuffer()

    if args.mode == "live":
        Config.SERIAL_PORT = args.serial
        acq = AcquisitionThread(ring)
    else:  # file
        if not args.input:
            parser.error("--input required when --mode file")
        acq = FileAcquisitionThread(
            ring,
            filepath=args.input,
            loop=args.loop,
            realtime=True,              # keep 250 Hz pacing
            chunk_size=Config.SAMPLE_RATE // 2,
        )

    power_mat = PowerMatrix()
    proc = ProcessingThread(ring, power_mat)
    synth = Sonifier()

    # ── kick everything off ──────────────────────────────────────────────── #
    print("Starting acquisition…")
    acq.start()
    proc.start()

    device_idx = pick_device(Config.OUTPUT_DEVICE, Config.AUDIO_HOST)
    print(f"Using audio device: {device_idx if device_idx is not None else 'default'}")

    def callback(outdata, frames, timeinfo, status):
        z = power_mat.fetch()          # (8, 5) z-scores 0–1
        outdata[:] = synth(z, frames) if z.size else np.zeros_like(outdata)

    with sd.OutputStream(
        samplerate=Config.FS_AUDIO,
        blocksize=Config.BLOCKSIZE,
        channels=2,
        dtype='float32',
        callback=callback,
        device=device_idx,
        latency='low',
    ):
        print("Streaming audio…  Press Ctrl-C to quit.")
        try:
            while acq.is_alive():
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