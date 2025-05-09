"""
All project-wide constants live here.
Feel free to edit SERIAL_PORT, AUDIO_HOST, mapping tables, etc.
"""

class Config:
    # ── OpenBCI board ─────────────────────────────────────────────
    SERIAL_PORT = "COM5"         # <- change to your Cyton dongle
    BOARD_ID    = 0              # 0 = Cyton
    SAMPLE_RATE = 250            # Hz (Cyton default)

    # ── Audio I/O (PortAudio) ─────────────────────────────────────
    AUDIO_HOST    = "Windows WASAPI"   # "ASIO" after you install ASIO4ALL
    OUTPUT_DEVICE = None               # substring match or None for default
    FS_AUDIO      = 48_000             # Hz
    BLOCKSIZE     = 512                # samples per callback

    # ── EEG → music mapping ───────────────────────────────────────
    BANDS = {
        "delta": (1, 4),
        "theta": (4, 8),
        "alpha": (8, 13),
        "beta":  (13, 30),
        "gamma": (30, 45),
    }
    CHANNEL_DEGREES = [0, 2, 4, 5, 7, 9, 11, 12]  # C-major scale (semitones)
    BASE_MIDI = {
        "delta": 36,  # C2
        "theta": 48,  # C3
        "alpha": 60,  # C4
        "beta":  72,  # C5
        "gamma": 84,  # C6
    }

    # ── Processing parameters ─────────────────────────────────────
    PROCESS_INTERVAL = 0.25   # s between power updates
    CALIBRATION_SEC  = 10     # baseline duration (eyes open)

    # ── Misc ──────────────────────────────────────────────────────
    QUEUE_MAXLEN = 20
