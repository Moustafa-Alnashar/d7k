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
SAMPLE_RATE = 8000
ROOT = "samples/"

# Math constraints matching your ATmega configuration
FRAME_SIZE = 128
N_FEATURES = 99
TOTAL_SAMPLES = FRAME_SIZE * N_FEATURES  # Exactly 12,672 samples (~1.584 seconds)

# Handshake configuration
SYNC_TOKEN = b"START_STREAM\n"  # Make sure your C code sends this exactly!

WORDS = sorted([
    d for d in os.listdir(ROOT) 
    if os.path.isdir(os.path.join(ROOT, d)) and not d.startswith('.')
])

if not WORDS:
    print(f"Error: No word folders found inside '{ROOT}'. Please create them first.")
    exit()

current_word_idx = 0
print(f"Current word: '{WORDS[current_word_idx]}'")
sample_count = np.zeros(len(WORDS), dtype=int) - 1

# Initialize Serial
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=5)

# Initialize PyAudio for Real-Time Output
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt8, channels=1, rate=SAMPLE_RATE, output=True)

print("\n--- CONTROLS ---")
print("Press [SPACEBAR] to TOGGLE armed recording mode.")
print("Press [N] for next word, [P] for previous word.")
print("Press Ctrl+C in the terminal to exit.\n")

is_armed = False

try:
    while True:
        # Navigation logic
        if keyboard.is_pressed('n'):
            current_word_idx = (current_word_idx + 1) % len(WORDS)
            print(f"Switched to next word: '{WORDS[current_word_idx]}'")
            time.sleep(0.3)
        elif keyboard.is_pressed('p'):
            current_word_idx = (current_word_idx - 1) % len(WORDS)
            print(f"Switched to previous word: '{WORDS[current_word_idx]}'")
            time.sleep(0.3)

        # Toggle armed state via Spacebar
        if keyboard.is_pressed('space'):
            is_armed = not is_armed
            if is_armed:
                print("🔴 SYSTEM ARMED: Waiting for ATmega transmission notification...")
                ser.reset_input_buffer()  # Flush old data while arming
            else:
                print("⚪ SYSTEM DISARMED: Recording cancelled.")
            time.sleep(0.4)  # Debounce spacebar toggle

        # If armed, look for the ATmega handshake notification
        if is_armed:
            # Check if there is enough data in buffer to at least read the sync token
            if ser.in_waiting >= len(SYNC_TOKEN):
                # Peek or read line to find token
                line = ser.readline()
                
                if SYNC_TOKEN in line:
                    print("⚡ Sync received! Recording exactly 1.58s batch...")
                    
                    sample_count[current_word_idx] += 1
                    word = WORDS[current_word_idx]
                    FINAL_WAV = f"{ROOT}{word}/{word}_sample_{sample_count[current_word_idx]}.wav"
                    
                    # Read the absolute structural frame package size directly
                    raw_data = ser.read(TOTAL_SAMPLES)
                    
                    if len(raw_data) < TOTAL_SAMPLES:
                        print(f"⚠️ Warning: Timeout! Only received {len(raw_data)}/{TOTAL_SAMPLES} bytes.")
                    
                    # Convert to your preferred clean signed format
                    temp = np.frombuffer(raw_data, dtype=np.uint8).astype(np.int16)
                    centered = (temp - 128).astype(np.int8)
                    data_bytes = centered.tobytes()
                    
                    # Save WAV
                    with wave.open(FINAL_WAV, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(1) 
                        wf.setframerate(SAMPLE_RATE)
                        wf.writeframes(data_bytes)
                    
                    print(f"🎉 Success! File saved: {FINAL_WAV}")
                    
                    # Automatically disarm system after a successful batch capture
                    # is_armed = False
                    # print("⚪ System disarmed. Press Spacebar to arm for next sample.")
                    
        time.sleep(0.01)

except KeyboardInterrupt:
    print("\nExiting script...")

finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
    ser.close()