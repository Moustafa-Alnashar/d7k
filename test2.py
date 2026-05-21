import serial
import numpy as np
import librosa
import wave

SERIAL_PORT = 'COM3'  # Update to match your setup
BAUD_RATE = 115200
SAMPLE_RATE = 8000
TRUE_DC_OFFSET = 128  # Must match C configuration

# The MCU processes 99 consecutive frames of 128 samples each
FRAME_SIZE = 128
HOP_SIZE = 128
N_FEATURES = 99
TOTAL_SAMPLES = FRAME_SIZE * N_FEATURES  # 12,672 samples (~1.58 seconds)

FINAL_WAV = "batch_recording.wav"


def extract_zcr_ste(filepath, target_sr=8000, frame_size=128, hop_size=128):
    """
    Extracts features using Librosa configured to match the hardware's
    exact non-overlapping framing windows.
    """
    # 8-bit WAV files are unsigned PCM. librosa.load automatically scales it to [-1.0, 1.0]
    y, sr = librosa.load(filepath, sr=target_sr, mono=True)
    
    # Critical Fix: Do not use librosa.effects.trim(). 
    y_trimmed, _ = librosa.effects.trim(y, top_db=15)

    target_len = int(target_sr * 1.0)

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
    # Trimming removes silence from the start/end, which destroys alignment with the raw MCU data.
    
    # Enforce exact temporal length to match N_FEATURES * FRAME_SIZE
    if len(y) < TOTAL_SAMPLES:
        y_fixed = np.pad(y, (0, TOTAL_SAMPLES - len(y)))
    else:
        y_fixed = y[:TOTAL_SAMPLES]

    # Pre-emphasis Filter (matching the C code logic)
    y_fixed = librosa.effects.preemphasis(y_fixed, coef=0.95)

    # Frame the data identically to the MCU (no overlap)
    frames = librosa.util.frame(y_fixed, frame_length=frame_size, hop_length=hop_size)

    # Calculate Zero Crossing Rate (center=False ensures the windows match step-for-step)
    zcr = librosa.feature.zero_crossing_rate(y_fixed, frame_length=frame_size, hop_length=hop_size, center=False)[0]
    
    # Short-Time Energy matching the scaled energy calculation
    ste = np.mean(frames**2, axis=0)

    # Keep exactly the frame size we expect
    zcr = zcr[:N_FEATURES]
    ste = ste[:N_FEATURES]

    return zcr, ste

def data_generator(data):
    for d in data:
        yield d


def capture_audio_features_c(data):
    zcr_out, ste_out = np.zeros(N_FEATURES), np.zeros(N_FEATURES)
    current_raw_sample = data_generator(data)
    
    for frame in range(N_FEATURES):
        energy = 0.0
        zero_crossings = 0
        last_centered = 0.0
        last_sample = 0.0

        for i in range(128):
            reading = next(current_raw_sample)
            
            centered = (reading.astype(np.int16) - TRUE_DC_OFFSET).astype(np.int8)
            centered = centered.astype(np.uint8)
            centered = (centered.astype(np.float32) - 128) / 128

            sample = centered - 0.95 * last_centered
            energy += sample * sample

            if i > 0:
                current_sign = (sample < 0.0)
                last_sign = (last_sample < 0.0)
                
                if current_sign != last_sign:
                    zero_crossings += 1            
            
            last_sample = sample
            last_centered = centered
        
        zcr_out[frame] = zero_crossings / 128.0
        ste_out[frame] = energy / 128.0

    return zcr_out, ste_out


def process_and_align():
    """
    Simulates the exact digital signal processing pipeline on raw data 
    to match the embedded chip's execution strategy.
    """
    print(f"Opening port {SERIAL_PORT}. Reading {TOTAL_SAMPLES} bytes...")
    
    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=15) as ser:
        # We explicitly read the total expected bytes for 99 frames
        raw_data = ser.read(TOTAL_SAMPLES)

    temp = np.frombuffer(raw_data, dtype=np.uint8).astype(np.int16)
    print(f"Raw Hardware Stats: Min={temp.min()}, Max={temp.max()}, Mean={temp.mean():.2f}")
    centered = (temp - 128).astype(np.int8)
    
    # Save raw incoming bytes cleanly as a standard WAV file
    with wave.open(FINAL_WAV, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(1)  # 1 byte = 8-bit Unsigned PCM Audio
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(centered.tobytes())  # Write original raw data to preserve exact byte values for Librosa analysis

    # Process via both implementations
    avr_zcr_val, avr_ste_val = capture_audio_features_c(temp)
    python_zcr_val, python_ste_val = extract_zcr_ste(FINAL_WAV, target_sr=SAMPLE_RATE, frame_size=FRAME_SIZE, hop_size=HOP_SIZE)

    # Global metrics computed over the entire capture run for alignment visibility
    mcu_mean_zcr = np.mean(avr_zcr_val)
    py_mean_zcr = np.mean(python_zcr_val)
    mcu_mean_ste = np.mean(avr_ste_val)
    py_mean_ste = np.mean(python_ste_val)

    # --- Print Sync Alignment Verification Report ---
    print("=" * 65)
    print("         BATCH EMBEDDED ML ALIGNMENT REPORT         ")
    print("=" * 65)
    print("Metric            | ATmega (C Code)   | Python (Librosa DSP)")
    print("------------------+-------------------+----------------------")
    print(f"Total Samples     | {len(temp):<17} | {TOTAL_SAMPLES:<20}")
    print(f"Mean ZCR Value    | {mcu_mean_zcr:.5f}           | {py_mean_zcr:.5f}")
    print(f"Mean STE Value    | {mcu_mean_ste:.5f}           | {py_mean_ste:.5f}")
    print("------------------+-------------------+----------------------")
    
    # We allow a minute epsilon margin for float precision variations across engines
    if np.allclose(avr_zcr_val, python_zcr_val, atol=1e-2):
        print("🎉 SUCCESS: Math execution blocks match up perfectly!")
    else:
        print("⚠️ MISMATCH: Structural array variation found. Check frame offsets.")
        print(f"Sample MCU frame 0 ZCR: {avr_zcr_val[0]:.4f} vs Librosa: {python_zcr_val[0]:.4f}")
    print("=" * 65)


if __name__ == "__main__":
    process_and_align()