# test_brainflow.py  – quick Cyton link check
from brainflow.board_shim import BoardShim, BrainFlowInputParams
import time

params = BrainFlowInputParams()
params.serial_port = "COM5"      # ← change if Device Manager shows a different COM#
board = BoardShim(0, params)     # 0 = Cyton

print("Preparing session …")
board.prepare_session()
board.start_stream()
time.sleep(2)                    # collect ~500 samples at 250 Hz
samples = board.get_board_data().shape[1]
print(f"Samples read in 2 s: {samples}")

board.stop_stream()
board.release_session()
