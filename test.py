import serial
import numpy as np
import librosa
import wave

SERIAL_PORT = 'COM3'  # Update to match your setup
BAUD_RATE = 115200
CHUNK_SIZE = 1024
SAMPLE_RATE = 8000
TRUE_DC_OFFSET = 128  # Must match the C true_dc_offset value

FINAL_WAV = "test_recording.wav"

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

    ste = ste / (frame_size * 128 * 128)

    return zcr, ste

def verify_alignment():
    print(f"Opening port {SERIAL_PORT}. Press your ATmega hardware button to sample...")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=10)
    
    raw_samples = []
    avr_zcr = 0.0
    avr_crossings = 0
    inside_frame = False
    reading_data = False

    while True:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        
        if "--- START FRAME ---" in line:
            inside_frame = True
            raw_samples = []
            continue
            
        if inside_frame:
            if line.startswith("AVR_ZCR:"):
                avr_zcr = float(line.split(":")[1].strip())
            elif line.startswith("AVR_CROSSINGS:"):
                avr_crossings = int(line.split(":")[1].strip())
            elif "RAW_DATA:" in line:
                reading_data = True
            elif "--- END FRAME ---" in line:
                break
            elif reading_data:
                if line.isdigit():
                    print(f"Received raw sample: {line}")
                    raw_samples.append(int(line))

    ser.close()

    if len(raw_samples) != 128:
        print(f"Error: Expected 128 samples, but received {len(raw_samples)}.")
        return

    temp = np.array(raw_samples, dtype=np.uint8).astype(np.int16)
    centered = (temp - 128).astype(np.int8)
    data_bytes = centered.tobytes()

    wf = wave.open(FINAL_WAV, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(1) # 1 byte per sample = 8-bit Audio
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(data_bytes)
    wf.close()

    # ----------------------------------------------------
    # FIX 3: Unpack your feature tuple safely
    # extract_zcr_ste returns a tuple: (zcr, ste). We only want zcr.
    # ----------------------------------------------------
    python_zcr, _ = extract_zcr_ste(FINAL_WAV)
    
    # Extract the scalar item from the output vector array
    python_zcr_val = python_zcr[0] 
    python_crossings = int(round(python_zcr_val * 128))

    # --- Display Detailed Verification Report ---
    print("\n" + "="*45)
    print("        EMBEDDED ML ALIGNMENT REPORT        ")
    print("="*45)
    print(f"Metric            | ATmega (C)   | Python (Librosa)")
    print(f"------------------+--------------+-----------------")
    print(f"Zero Crossings    | {avr_crossings:<12} | {python_crossings:<15}")
    print(f"Final ZCR Feature | {avr_zcr:.4f}        | {python_zcr_val:.4f}")
    print(f"------------------+--------------+-----------------")
    
    if avr_crossings == python_crossings:
        print("Success: Math structures match exactly!")
    else:
        print("Mismatch: Check for subtle differences in padding or trimming boundaries.")
    print("="*45)

if __name__ == "__main__":
    verify_alignment()