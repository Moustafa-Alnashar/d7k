import serial
import wave
import numpy as np
import time
import librosa

# Import your unchanged Python function
def extract_zcr_ste(filepath, target_sr=8000, duration=1.0, frame_size=128, hop_size=128):
    y, sr = librosa.load(filepath, sr=target_sr, mono=True)
    y_trimmed, _ = librosa.effects.trim(y, top_db=15)

    target_len = int(target_sr * duration)

    if len(y_trimmed) < target_len:
        pad_total = target_len - len(y_trimmed)
        pad_left = pad_total // 2
        pad_right = pad_total - pad_left
        y_fixed = np.pad(y_trimmed, (pad_left, pad_right))
    else:
        cut_total = len(y_trimmed) - target_len
        cut_left = cut_total // 2
        cut_right = cut_total - cut_left
        y_fixed = y_trimmed[cut_left : len(y_trimmed) - cut_right]

    # Pre-emphasis Filter
    y_fixed = librosa.effects.preemphasis(y_fixed, coef=0.95)

    frames = librosa.util.frame(y_fixed, frame_length=frame_size, hop_length=hop_size)

    zcr = librosa.feature.zero_crossing_rate(y_fixed, frame_length=frame_size, hop_length=hop_size, center=False)[0]
    ste = np.mean(frames**2, axis=0)

    min_len = min(len(zcr), len(ste))
    zcr = zcr[:min_len]
    ste = ste[:min_len]

    # print(f"Extracted features from '{os.path.basename(filepath)}': ZCR min={zcr.min():.3f}, max={zcr.max():.3f}, mean={zcr.mean():.3f} | STE min={ste.min():.6f}, max={ste.max():.6f}, mean={ste.mean():.6f}")
    # temp_zcr = zcr.copy()
    # temp_ste = ste.copy()

    # smooth_window = 5
    # zcr = np.convolve(zcr, np.ones(smooth_window)/smooth_window, mode='same')
    # ste = np.convolve(ste, np.ones(smooth_window)/smooth_window, mode='same')

    # print(f"Max differences - ZCR: {np.max(temp_zcr - zcr)}, STE: {np.max(temp_ste - ste)}")

    ste = ste / (frame_size * 128 * 128)

    return zcr, ste

# Configuration 
SERIAL_PORT = 'COM3'
BAUD_RATE = 115200
SAMPLE_RATE = 8000
N_FEATURES = 10
SAMPLES_PER_FRAME = 128
TOTAL_SAMPLES = N_FEATURES * SAMPLES_PER_FRAME

def capture_and_process():
    print(f"Connecting to ATmega32A on {SERIAL_PORT}...")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=5)
    time.sleep(2) # Allow ATmega to reset

    # ----------------------------------------------------
    # 1. RECEIVE RAW AUDIO FROM ATMEGA32A
    # ----------------------------------------------------
    print(f"Waiting to receive {TOTAL_SAMPLES} raw audio bytes...")
    
    # Read exactly the number of bytes capture_audio_features sends
    raw_data = ser.read(TOTAL_SAMPLES)
    
    if len(raw_data) < TOTAL_SAMPLES:
        print(f"Error: Only received {len(raw_data)} bytes. Check hardware.")
        ser.close()
        return

    # ----------------------------------------------------
    # 2. SAVE AS .WAV FILE
    # ----------------------------------------------------
    wav_path = 'captured_from_atmega.wav'
    raw_np = np.frombuffer(raw_data, dtype=np.uint8)
    
    # Center the raw 8-bit data (-128) just like your pipeline
    centered = (raw_np.astype(np.int16) - 128).astype(np.int8)

    with wave.open(wav_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(1) # 8-bit PCM
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(centered.tobytes())
        
    print(f"Audio successfully saved to {wav_path}")

    # ----------------------------------------------------
    # 3. READ C CALCULATION RESULTS
    # ----------------------------------------------------
    print("Reading ATmega32A calculation results...")
    c_output = []
    while True:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if "---END---" in line:
            break
        if line and "RESULTS" not in line:
            c_output.append(line)
            
    ser.close()

    # ----------------------------------------------------
    # 4. RUN UNCHANGED PYTHON FUNCTION & PRINT BOTH
    # ----------------------------------------------------
    python_output = extract_zcr_ste(wav_path)

    print("\n=== OUTPUT FROM C (ATMEGA32A) ===")
    for result in c_output:
        print(result)

    print("\n=== OUTPUT FROM PYTHON ===")
    print(python_output)

if __name__ == "__main__":
    capture_and_process()
