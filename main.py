import serial
import numpy as np
import wave
import os
import pyaudio  # New import for playback
from pydub import AudioSegment

# Configuration
SERIAL_PORT = 'COM3' 
BAUD_RATE = 115200
CHUNK_SIZE = 1024
SAMPLE_RATE = 8000
TEMP_WAV = "temp_recording.wav"
FINAL_MP3 = "whatsapp_voice.mp3"

# Initialize Serial
ser = serial.Serial(SERIAL_PORT, BAUD_RATE)

# Initialize PyAudio for Real-Time Output
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt8,  # Matches your centered_data
                channels=1,
                rate=SAMPLE_RATE,
                output=True)

# Initialize Wave File
wf = wave.open(TEMP_WAV, 'wb')
wf.setnchannels(1)
wf.setsampwidth(1) 
wf.setframerate(SAMPLE_RATE)

print("Streaming, Recording, and Playing... Press Ctrl+C to stop.")

try:
    while True:
        raw_data = ser.read(CHUNK_SIZE)
        if not raw_data:
            continue

        # Convert uint8 (0-255) to int8 (-128 to 127)
        raw = np.frombuffer(raw_data, dtype=np.uint8).astype(np.int16)
        centered = (raw - 128).astype(np.int8)

        # 1. Save to File
        data_bytes = centered.tobytes()
        wf.writeframes(data_bytes)
        
        # 2. Play in Real-Time
        # stream.write(data_bytes)

except KeyboardInterrupt:
    print("\nProcessing audio for WhatsApp...")

finally:
    # Cleanup Playback
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Cleanup File and Serial
    wf.close()
    ser.close()

    # --- CONVERSION STEP ---
    if os.path.exists(TEMP_WAV):
        try:
            audio = AudioSegment.from_wav(TEMP_WAV)
            audio.export(FINAL_MP3, format="mp3", bitrate="128k")
            print(f"Success! '{FINAL_MP3}' is ready.")
        except Exception as e:
            print(f"Error during conversion: {e}")