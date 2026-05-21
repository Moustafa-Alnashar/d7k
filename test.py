import serial
import numpy as np
import wave

SERIAL_PORT = 'COM3'  # Update to match your setup
BAUD_RATE = 115200
CHUNK_SIZE = 128*99  # Read enough for 99 frames of 128 samples each
SAMPLE_RATE = 8000

FINAL_WAV = "test_recording.wav"

with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=5) as ser:
    print("Waiting for data from the ATmega...")
    while ser.readline().decode('utf-8', errors='ignore').strip().find("---start---") == -1:  # Wait for the first line of data to ensure the device is sending
        pass
    raw_data = ser.read(CHUNK_SIZE)  # Read 128 bytes of raw data

temp = np.frombuffer(raw_data, dtype=np.uint8).astype(np.int16)
centered = (temp - 128).astype(np.int8)

with wave.open(FINAL_WAV, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(1) # 1 byte per sample = 8-bit Audio
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(centered.tobytes())

    print(f"Saved raw data to {FINAL_WAV} for analysis.")