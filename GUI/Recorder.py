import sys
import os
import wave
import time
import serial
import numpy as np
import pyaudio

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTextEdit
)
from PySide6.QtGui import QFont, QKeyEvent

# Configuration
SERIAL_PORT = 'COM3' 
BAUD_RATE = 115200
SAMPLE_RATE = 8000
ROOT = "../samples/"

FRAME_SIZE = 128
N_FEATURES = 99
TOTAL_SAMPLES = FRAME_SIZE * N_FEATURES  # Exactly 12,672 samples (~1.584 seconds)
SYNC_TOKEN = b"START_STREAM\n"

class SerialWorker(QObject):
    """Handles the serial handshake and data streaming on a background thread."""
    status_message = Signal(str)
    sample_saved = Signal(str, int)  # word, new_count
    
    def __init__(self, port, baudrate, root_dir):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.root_dir = root_dir
        self.is_running = True
        self.is_armed = False
        self.current_word = ""
        self.sample_counts = {}
        
        # Initialize PyAudio for real-time validation playback
        self.p = pyaudio.PyAudio()
        self.audio_stream = self.p.open(format=pyaudio.paInt8, channels=1, rate=SAMPLE_RATE, output=True)
        
        # Open Serial Port
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=2)
        except Exception as e:
            self.ser = None
            print(f"Serial Connection Error: {e}")

    @Slot(str, dict)
    def update_state(self, current_word, sample_counts):
        """Receives updates from the main GUI thread safely."""
        self.current_word = current_word
        self.sample_counts = sample_counts

    @Slot(bool)
    def set_armed(self, armed):
        self.is_armed = armed
        if self.ser and armed:
            self.ser.reset_input_buffer()  # Flush stale inputs on fresh arming

    def run_loop(self):
        """Main worker loop running inside the QThread."""
        if not self.ser:
            self.status_message.emit(f"⚠️ Error: Could not open serial port {self.port}")
            return

        self.status_message.emit("🔌 Serial Port connected successfully.")
        
        while self.is_running:
            if self.is_armed and self.current_word:
                try:
                    if self.ser.in_waiting >= len(SYNC_TOKEN):
                        line = self.ser.readline()
                        
                        if SYNC_TOKEN in line:
                            self.status_message.emit("⚡ Sync received! Recording batch...")
                            
                            # Read exact structural package
                            raw_data = self.ser.read(TOTAL_SAMPLES)
                            
                            if len(raw_data) < TOTAL_SAMPLES:
                                self.status_message.emit(f"⚠️ Warning: Timeout! Only got {len(raw_data)}/{TOTAL_SAMPLES} bytes.")
                                continue
                            
                            # Update counters safely inside worker copy
                            self.sample_counts[self.current_word] += 1
                            count = self.sample_counts[self.current_word]
                            
                            # Processing DSP mathematics
                            temp = np.frombuffer(raw_data, dtype=np.uint8).astype(np.int16)
                            centered = (temp - 128).astype(np.int8)
                            data_bytes = centered.tobytes()
                            
                            # Save the audio sample
                            word_dir = os.path.join(self.root_dir, self.current_word)
                            final_wav = os.path.join(word_dir, f"{self.current_word}_sample_{count}.wav")
                            
                            with wave.open(final_wav, 'wb') as wf:
                                wf.setnchannels(1)
                                wf.setsampwidth(1) 
                                wf.setframerate(SAMPLE_RATE)
                                wf.writeframes(data_bytes)
                            
                            # Play audio validation back to user
                            self.audio_stream.write(data_bytes)
                            
                            # Notify the UI thread
                            self.sample_saved.emit(self.current_word, count)
                except Exception as e:
                    self.status_message.emit(f"❌ Error during reading: {e}")
            
            time.sleep(0.01)  # Context switch break to prevent CPU choking

    def cleanup(self):
        """Safely close raw resource lifecycles."""
        self.is_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        self.p.terminate()


class AudioDataCollectorGUI(QMainWindow):
    # Signals used to talk to our worker thread cleanly
    state_changed_signal = Signal(str, dict)
    arm_changed_signal = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ATmega Data Collector Sandbox")
        self.resize(550, 450)
        
        # Load directory mappings
        self.words = sorted([
            d for d in os.listdir(ROOT) 
            if os.path.isdir(os.path.join(ROOT, d)) and not d.startswith('.')
        ])
        
        if not self.words:
            print(f"Error: No word folders found inside '{ROOT}'. Check environment setup.")
            sys.exit(1)
            
        # Parse directories dynamically to discover current counts
        self.sample_counts = {}
        for w in self.words:
            word_dir = os.path.join(ROOT, w)
            existing_files = [f for f in os.listdir(word_dir) if f.endswith('.wav') and f.startswith(f"{w}_sample_")]
            if existing_files:
                # Find maximum index to prevent overwriting past recorded sessions
                indexes = [int(f.split('_sample_')[-1].replace('.wav', '')) for f in existing_files]
                self.sample_counts[w] = max(indexes)
            else:
                self.sample_counts[w] = -1

        self.is_armed = False
        self.init_ui()
        self.init_worker_thread()

    def init_ui(self):
        # Central widget configuration
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Header Info
        self.word_label = QLabel("Active Target Word:")
        self.word_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        
        # Word Selector Dropdown
        self.word_selector = QComboBox()
        self.word_selector.addItems(self.words)
        self.word_selector.currentIndexChanged.connect(self.on_word_selection_changed)
        self.word_selector.setFocusPolicy(Qt.FocusPolicy.NoFocus) # Keeps spacebar mapped to arming instead of combo dropdown
        
        # Counter Status Box
        self.counter_label = QLabel()
        self.counter_label.setFont(QFont("Arial", 11))
        self.update_counter_display()

        # Arm Button Layout
        self.arm_button = QPushButton("⚪ SYSTEM DISARMED (Press Space to Arm)")
        self.arm_button.setCheckable(True)
        self.arm_button.setStyleSheet("background-color: #90878E; min-height: 45px; font-weight: bold; font-size: 13px;")
        self.arm_button.clicked.connect(self.toggle_arm_state)
        self.arm_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Navigation Layout Buttons
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Previous (Left Arrow)")
        self.next_btn = QPushButton("Next (Right Arrow) ▶")
        self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_btn.clicked.connect(self.previous_word)
        self.next_btn.clicked.connect(self.next_word)
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)

        # Logging Terminal Frame
        self.log_terminal = QTextEdit()
        self.log_terminal.setReadOnly(True)
        self.log_terminal.setPlaceholderText("System logs will print out here...")
        
        # Assemble overall frame architecture
        main_layout.addWidget(self.word_label)
        main_layout.addWidget(self.word_selector)
        main_layout.addWidget(self.counter_label)
        main_layout.addLayout(nav_layout)
        main_layout.addWidget(self.arm_button)
        main_layout.addWidget(QLabel("<b>Log Output:</b>"))
        main_layout.addWidget(self.log_terminal)

        self.setFocus()  # Ensure the main window captures key events

    def init_worker_thread(self):
        """Instantiates background system logic processing loop."""
        self.t = QThread()
        self.worker = SerialWorker(SERIAL_PORT, BAUD_RATE, ROOT)
        self.worker.moveToThread(self.t)
        
        # Wire up communication signals between Main GUI and Background Thread
        self.t.started.connect(self.worker.run_loop)
        self.worker.status_message.connect(self.log_to_terminal)
        self.worker.sample_saved.connect(self.on_sample_captured_callback)
        
        # Link internal controller updates to thread
        self.state_changed_signal.connect(self.worker.update_state)
        self.arm_changed_signal.connect(self.worker.set_armed)
        
        self.t.start()
        self.sync_state_to_worker()

    def sync_state_to_worker(self):
        """Passes current UI states downstream safely."""
        current_word = self.word_selector.currentText()
        self.state_changed_signal.emit(current_word, self.sample_counts.copy())

    def update_counter_display(self):
        word = self.word_selector.currentText()
        count = self.sample_counts.get(word, -1) + 1
        self.counter_label.setText(f"Next sample sequence will be saved as: <b>{word}_sample_{count}.wav</b>")

    def toggle_arm_state(self):
        self.is_armed = not self.is_armed
        self.arm_button.setChecked(self.is_armed)
        if self.is_armed:
            self.arm_button.setText("🔴 SYSTEM ARMED: Waiting for ATmega handshake...")
            self.arm_button.setStyleSheet("background-color: #ff4d4d; color: white; min-height: 45px; font-weight: bold; font-size: 13px;")
            self.log_to_terminal("System Armed. Listening for serial sync token data package...")
        else:
            self.arm_button.setText("⚪ SYSTEM DISARMED (Press Space to Arm)")
            self.arm_button.setStyleSheet("background-color: #90878E; color: black; min-height: 45px; font-weight: bold; font-size: 13px;")
            self.log_to_terminal("System Disarmed.")
        
        self.arm_changed_signal.emit(self.is_armed)

    def next_word(self):
        idx = (self.word_selector.currentIndex() + 1) % self.word_selector.count()
        self.word_selector.setCurrentIndex(idx)

    def previous_word(self):
        idx = (self.word_selector.currentIndex() - 1) % self.word_selector.count()
        if idx < 0:
            idx = self.word_selector.count() - 1
        self.word_selector.setCurrentIndex(idx)

    def on_word_selection_changed(self):
        self.update_counter_display()
        self.sync_state_to_worker()
        self.log_to_terminal(f"Switched target word configuration to: '{self.word_selector.currentText()}'")

    @Slot(str, int)
    def on_sample_captured_callback(self, word, new_count):
        """Triggered from worker thread whenever a complete WAV gets saved successfully."""
        self.sample_counts[word] = new_count
        self.update_counter_display()
        self.log_to_terminal(f"🎉 Success! File saved: {ROOT}{word}/{word}_sample_{new_count}.wav")
        
        # If you want to automatically disarm after capture, uncomment below lines:
        # self.toggle_arm_state()

    @Slot(str)
    def log_to_terminal(self, text):
        self.log_terminal.append(text)
        # Auto scroll to bottom
        self.log_terminal.ensureCursorVisible()

    def keyPressEvent(self, event: QKeyEvent):
        """Intercepts keyboard strokes mapping shortcuts directly onto control actions."""
        print(f"Key Pressed: {event.text()} (Code: {event.key()})")
        if event.key() == Qt.Key.Key_Space:
            self.toggle_arm_state()
            event.accept()
        elif event.key() == Qt.Key.Key_Left:
            self.previous_word()
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            self.next_word()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Runs hook window destructions making sure threads exit loop safely."""
        self.worker.cleanup()
        self.t.quit()
        self.t.wait()
        event.accept()


if __name__ == "__main__":
    # Fallback structure logic loop creation
    if not os.path.exists(ROOT):
        os.makedirs(ROOT)
        
    app = QApplication(sys.argv)
    window = AudioDataCollectorGUI()
    window.show()
    sys.exit(app.exec())