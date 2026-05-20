import serial
import numpy as np
import wave
import pyaudio
import keyboard
import time
import os

# Configuration
SERIAL_PORT = 'COM3' 
BAUD_RATE = 115200
CHUNK_SIZE = 1024
SAMPLE_RATE = 8000
ROOT = "samples/"

WORDS = sorted([
    d for d in os.listdir(ROOT) 
    if os.path.isdir(os.path.join(ROOT, d)) and not d.startswith('.')
])
current_word_idx = 0
print(f"Current word: '{WORDS[current_word_idx]}'")
sample_count = np.zeros(len(WORDS), dtype=int) - 1 # Start at -1 so first increment sets to 0

# Initialize Serial
ser = serial.Serial(SERIAL_PORT, BAUD_RATE)

# Initialize PyAudio for Real-Time Output
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt8,
                channels=1,
                rate=SAMPLE_RATE,
                output=True)

print("Hold [SPACEBAR] to record to RAM. Release to save MP3.")
print("Press Ctrl+C in the terminal to exit.")

recording = False
wf = None

try:
    while True:
        if keyboard.is_pressed('n'):
            current_word_idx = (current_word_idx + 1) % len(WORDS)
            print(f"Switched to next word: '{WORDS[current_word_idx]}'")
            time.sleep(0.3)  # Debounce delay
        elif keyboard.is_pressed('p'):
            current_word_idx = (current_word_idx - 1) % len(WORDS)
            print(f"Switched to previous word: '{WORDS[current_word_idx]}'")
            time.sleep(0.3)  # Debounce delay

        if keyboard.is_pressed('space'):
            if not recording:
                print("\nRecording started (saving to RAM)...")
                sample_count[current_word_idx] += 1
                ser.reset_input_buffer() 

                FINAL_WAV = f"{ROOT}{WORDS[current_word_idx]}/{WORDS[current_word_idx]}_sample_{sample_count[current_word_idx]}.wav"
                wf = wave.open(FINAL_WAV, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(1) 
                wf.setframerate(SAMPLE_RATE)
                recording = True

            if ser.in_waiting >= CHUNK_SIZE:
                raw_data = ser.read(CHUNK_SIZE)
                
                # Convert uint8 (0-255) to int8 (-128 to 127)
                temp = np.frombuffer(raw_data, dtype=np.uint8).astype(np.int16)
                centered = (temp - 128).astype(np.int8)
                data_bytes = centered.tobytes()
                        
                wf.writeframes(data_bytes)

                # centered_uint8 = centered.astype(np.uint8)
                # manual_norm = (centered_uint8.astype(np.float32) - 128) / 128
                # print(f'Manual normalization: min={manual_norm.min():.3f}, max={manual_norm.max():.3f}, mean={manual_norm.mean():.3f}')

                
                # 2. Play in Real-Time
                # stream.write(data_bytes)
        
        else:
            if recording:
                print("Recording stopped. Exporting WAV...")
                recording = False
                
                wf.close() 
                wf = None
                
                print(f"Success! '{FINAL_WAV}' is updated.")
                
            time.sleep(0.01)

except KeyboardInterrupt:
    print("\nExiting script...")

finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
    if wf:
        wf.close()
    ser.close()