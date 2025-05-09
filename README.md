# EEG‑Sonify (minimal prototype)

## Quick start

1.  **Install Python ≥ 3.10**  
    ```powershell
    python -m venv eeg-env
    eeg-env\Scripts\activate

    python -m pip install --upgrade pip

    cd "C:\Users\k2477674\Documents\eeg_sonify"

    pip install -r requirements.txt
    ```

2.  **Plug your Cyton dongle** and note the COM port (e.g. `COM3`).  

3.  **Run**  
    ```powershell
    python main.py --serial COM5
    ```

4.  When prompted in the console, keep eyes open for 10 s (baseline), then the sonification will begin.

## File structure

* `config.py` — tweak ports, audio host, mapping tables  
* `acquire.py` — board I/O → ring buffer  
* `processing.py` — band power & z‑score worker  
* `synth.py` — additive synthesis mapping  
* `main.py` — top‑level application  

## Latency

This build uses Windows WASAPI shared mode by default.  
Install **ASIO4ALL** or a vendor ASIO driver and set

```python
AUDIO_HOST = "ASIO"
```

in `config.py` for best (< 20 ms) output latency.
