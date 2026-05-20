import numpy as np
import wave
import librosa
import os
import serial

# Configuration
SERIAL_PORT = 'COM3' 
BAUD_RATE = 115200
CHUNK_SIZE = 1024*32

# Initialize Serial
ser = serial.Serial(SERIAL_PORT, BAUD_RATE)

# Simulate ATmega data: range 24-107, 1 second at 8kHz
SAMPLE_RATE = 8000
DURATION = 1.0
N = int(SAMPLE_RATE * DURATION)
np.random.seed(42)
# raw = np.random.randint(24, 108, N).astype(np.uint8)

raw_data = ser.read(CHUNK_SIZE)
raw = np.frombuffer(raw_data, dtype=np.uint8)

# Center using (raw - 128), as in your pipeline
centered = (raw.astype(np.int16) - 128).astype(np.int8)

# Write to WAV as 8-bit PCM
wav_path = 'sim_test.wav'
with wave.open(wav_path, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(1)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(centered.tobytes())

# Read back with librosa
samples, sr = librosa.load(wav_path, sr=SAMPLE_RATE, mono=True)
print(f'Librosa output: min={samples.min():.3f}, max={samples.max():.3f}, mean={samples.mean():.3f}')

# Show what the original centered data would be if normalized manually
centered_uint8 = centered.astype(np.uint8)
manual_norm = (centered_uint8.astype(np.float32) - 128) / 128
print(f'Manual normalization: min={manual_norm.min():.3f}, max={manual_norm.max():.3f}, mean={manual_norm.mean():.3f}')

raw_norm = (raw.astype(np.float32) - 128) / 128
print(f'Raw normalization: min={raw_norm.min():.3f}, max={raw_norm.max():.3f}, mean={raw_norm.mean():.3f}')

# Clean up
# os.remove(wav_path)

# import librosa

# SAMPLE_PATH = "samples"
# SAMPLE_RATE = 8000
# wav_path = f"{SAMPLE_PATH}/ana/sample_0.wav"

# samples, sr = librosa.load(wav_path, sr=SAMPLE_RATE, mono=True)
# print(f'Librosa output: min={samples.min():.3f}, max={samples.max():.3f}, mean={samples.mean():.3f}')

# samples = librosa.effects.preemphasis(samples, coef=0.95)
# zcr = librosa.feature.zero_crossing_rate(samples, frame_length=160, hop_length=80, center=False)[0]
# print(f'ZCR: min={zcr.min():.3f}, max={zcr.max():.3f}, mean={zcr.mean():.3f}')