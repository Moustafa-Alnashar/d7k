import sys
import os
import numpy as np
import librosa
from sklearn.model_selection import train_test_split
from sklearn.cluster import KMeans

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QProgressBar, QDoubleSpinBox, QSpinBox
)
from PySide6.QtGui import QFont

# Structural Math Constraints matching your ATmega configurations
ROOT = "../"
SAMPLE_PATH = os.path.join(ROOT, "Samples")
EXPORT_PATH = os.path.join(ROOT, "exported_templates")
FRAME_SIZE = 128
N_FEATURES = 99
TOTAL_SAMPLES = FRAME_SIZE * N_FEATURES  # 12,672 samples (~1.58 seconds)


class TrainingWorker(QObject):
    """Background engine handling feature extraction, clustering, and export."""
    progress_update = Signal(int, str)  # percentage, log_text
    training_finished = Signal(float, str)  # accuracy, header_file_path
    training_failed = Signal(str)

    def __init__(self, templates_per_word, w_zcr):
        super().__init__()
        self.templates_per_word = templates_per_word
        self.w_zcr = w_zcr
        self.w_ste = 1.0 - w_zcr

    def extract_zcr_ste(self, filepath):
        """Processes a single WAV audio frame matrix."""
        y, sr = librosa.load(filepath, sr=8000, mono=True)

        if len(y) < TOTAL_SAMPLES:
            y_fixed = np.pad(y, (0, TOTAL_SAMPLES - len(y)))
        else:
            y_fixed = y[:TOTAL_SAMPLES]

        # Apply digital Pre-emphasis Filter
        y_fixed = librosa.effects.preemphasis(y_fixed, coef=0.95)
        y_fixed = y_fixed / 1.95  # Match scaling normalization
        
        frames = librosa.util.frame(y_fixed, frame_length=FRAME_SIZE, hop_length=FRAME_SIZE)

        zcr = librosa.feature.zero_crossing_rate(y_fixed, frame_length=FRAME_SIZE, hop_length=FRAME_SIZE, center=False)[0]
        ste = np.mean(frames**2, axis=0)

        return zcr[:N_FEATURES], ste[:N_FEATURES]

    def start_processing(self):
        try:
            if not os.path.exists(SAMPLE_PATH):
                self.training_failed.emit(f"Directory '{SAMPLE_PATH}' does not exist.")
                return

            words = sorted([
                d for d in os.listdir(SAMPLE_PATH) 
                if os.path.isdir(os.path.join(SAMPLE_PATH, d)) and not d.startswith('.')
            ])

            if not words:
                self.training_failed.emit("No word directories found within target path.")
                return

            self.progress_update.emit(5, f"Detected {len(words)} unique word classes: {words}")
            
            X_zcr, X_ste, Y = [], [], []

            # --- Step 1: Feature Extraction ---
            self.progress_update.emit(10, "Extracting features from audio recordings...")
            for word_idx, word_name in enumerate(words):
                word_dir = os.path.join(SAMPLE_PATH, word_name)
                files = [f for f in os.listdir(word_dir) if f.endswith('.wav')]
                
                for f in files:
                    filepath = os.path.join(word_dir, f)
                    try:
                        zcr, ste = self.extract_zcr_ste(filepath)
                        X_zcr.append(zcr)
                        X_ste.append(ste)
                        Y.append(word_idx)
                    except Exception as ex:
                        self.progress_update.emit(10, f"⚠️ Error processing {f}: {ex}")

            X_zcr = np.array(X_zcr)
            X_ste = np.array(X_ste)
            Y = np.array(Y)

            if len(Y) == 0:
                self.training_failed.emit("Zero usable WAV samples were parsed.")
                return

            self.progress_update.emit(30, f"Successfully loaded {len(Y)} total processing items.")

            # --- Step 2: Data Splitting ---
            X_zcr_train, X_zcr_test, X_ste_train, X_ste_test, Y_train, Y_test = train_test_split(
                X_zcr, X_ste, Y, test_size=0.20, random_state=42, stratify=Y
            )

            # --- Step 3: Clustering / Template Generation ---
            self.progress_update.emit(45, f"Running K-Means algorithm ({self.templates_per_word} clusters)...")
            zcr_templates, ste_templates, template_labels = [], [], []

            for i in range(len(words)):
                class_zcr = X_zcr_train[Y_train == i]
                class_ste = X_ste_train[Y_train == i]

                if len(class_zcr) < self.templates_per_word:
                    self.progress_update.emit(45, f"⚠️ Skip: Not enough samples for target label '{words[i]}'")
                    continue

                # Scale and combine features for K-Means processing
                combined_features = np.hstack((class_zcr * self.w_zcr, class_ste * self.w_ste))
                kmeans = KMeans(n_clusters=self.templates_per_word, random_state=42, n_init=10)
                kmeans.fit(combined_features)

                for k in range(self.templates_per_word):
                    center = kmeans.cluster_centers_[k]
                    # Compute nearest sample using Manhattan Distance
                    distances = np.sum(np.abs(combined_features - center), axis=1)
                    best_idx = np.argmin(distances)

                    zcr_templates.append(class_zcr[best_idx])
                    ste_templates.append(class_ste[best_idx])
                    template_labels.append(i)

            zcr_templates = np.array(zcr_templates)
            ste_templates = np.array(ste_templates)
            template_labels = np.array(template_labels)

            # --- Step 4: Cross-Validation Evaluation ---
            self.progress_update.emit(75, "Running pipeline testing on unseen test subset...")
            correct_predictions = 0
            total_predictions = len(Y_test)

            for i in range(total_predictions):
                test_zcr = X_zcr_test[i]
                test_ste = X_ste_test[i]
                true_label = Y_test[i]

                distances_zcr = np.sum(np.abs(zcr_templates - test_zcr), axis=1)
                distances_ste = np.sum(np.abs(ste_templates - test_ste), axis=1)

                total_distances = (self.w_zcr * distances_zcr) + (self.w_ste * distances_ste)
                predicted_index = total_distances.argmin()
                predicted_label = template_labels[predicted_index]

                if predicted_label == true_label:
                    correct_predictions += 1

            accuracy = (correct_predictions / total_predictions) * 100 if total_predictions > 0 else 0.0
            self.progress_update.emit(85, f"Accuracy evaluation complete: {accuracy:.2f}%")

            # --- Step 5: C Header File Export ---
            os.makedirs(EXPORT_PATH, exist_ok=True)
            header_path = os.path.join(EXPORT_PATH, "word_templates.h")
            
            num_templates = len(template_labels)
            num_frames = zcr_templates.shape[1]

            with open(header_path, "w", encoding="utf-8") as f:
                f.write("#ifndef WORD_TEMPLATES_H\n")
                f.write("#define WORD_TEMPLATES_H\n\n")
                f.write("#include <stdint.h>\n\n")
                f.write(f"#define N_WORDS {len(words)}\n")
                f.write(f"#define TEMPLATES_PER_WORD {self.templates_per_word}\n")
                f.write(f"#define TOTAL_TEMPLATES {num_templates}\n")
                f.write(f"#define N_FEATURES {num_frames}\n\n")

                f.write(f"const float W_STE = {self.w_ste:.4f}f;\n")
                f.write(f"const float W_ZCR = {self.w_zcr:.4f}f;\n\n")

                f.write("static const char* words[] = {\n    ")
                f.write(", ".join([f'"{w}"' for w in words]))
                f.write("\n};\n\n")

                f.write("const uint8_t template_labels[TOTAL_TEMPLATES] PROGMEM = {\n    ")
                f.write(", ".join([str(lbl) for lbl in template_labels]))
                f.write("\n};\n\n")

                f.write("const float zcr_templates[TOTAL_TEMPLATES][N_FEATURES] PROGMEM = {\n")
                for i in range(num_templates):
                    f.write(f"    // Template {i} - Word: {words[template_labels[i]]}\n    {{")
                    f.write(", ".join([f"{val:.4f}" for val in zcr_templates[i]]))
                    f.write("},\n")
                f.write("};\n\n")

                f.write("const float ste_templates[TOTAL_TEMPLATES][N_FEATURES] PROGMEM = {\n")
                for i in range(num_templates):
                    f.write(f"    // Template {i} - Word: {words[template_labels[i]]}\n    {{")
                    f.write(", ".join([f"{val:.4f}" for val in ste_templates[i]]))
                    f.write("},\n")
                f.write("};\n\n")

                f.write("#endif // WORD_TEMPLATES_H\n")

            self.progress_update.emit(100, "Header structural compilation file written.")
            self.training_finished.emit(accuracy, header_path)

        except Exception as e:
            self.training_failed.emit(str(e))


class AudioTrainingStudioGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Embedded DSP Template Trainer")
        self.resize(600, 500)
        
        self.t = None
        self.worker = None
        
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Parameter Hyperparameters Setup Area
        params_layout = QHBoxLayout()
        
        # Templates selector
        tpl_layout = QVBoxLayout()
        tpl_layout.addWidget(QLabel("Templates Per Word Class:"))
        self.sb_templates = QSpinBox()
        self.sb_templates.setRange(1, 20)
        self.sb_templates.setValue(4)
        tpl_layout.addWidget(self.sb_templates)
        
        # ZCR Weight selector
        zcr_layout = QVBoxLayout()
        zcr_layout.addWidget(QLabel("Zero Crossing Weight (W_ZCR):"))
        self.sb_w_zcr = QDoubleSpinBox()
        self.sb_w_zcr.setRange(0.0, 1.0)
        self.sb_w_zcr.setSingleStep(0.05)
        self.sb_w_zcr.setValue(0.60)
        self.sb_w_zcr.valueChanged.connect(self.sync_weights_ui)
        zcr_layout.addWidget(self.sb_w_zcr)

        # STE Weight readout
        ste_layout = QVBoxLayout()
        ste_layout.addWidget(QLabel("Energy Weight (W_STE Output):"))
        self.lbl_w_ste = QLabel("<b>0.40</b>")
        self.lbl_w_ste.setFont(QFont("Arial", 11))
        self.lbl_w_ste.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ste_layout.addWidget(self.lbl_w_ste)

        params_layout.addLayout(tpl_layout)
        params_layout.addLayout(zcr_layout)
        params_layout.addLayout(ste_layout)
        main_layout.addLayout(params_layout)

        # Operational Execution Button
        self.btn_run = QPushButton("🚀 Run Pipeline Training Extraction")
        self.btn_run.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.btn_run.setStyleSheet("background-color: #007acc; color: white; min-height: 40px;")
        self.btn_run.clicked.connect(self.execute_training_thread)
        main_layout.addWidget(self.btn_run)

        # Progress Status Metrics Tracker
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # Log Terminal Outputs Window frame
        self.log_terminal = QTextEdit()
        self.log_terminal.setReadOnly(True)
        self.log_terminal.setPlaceholderText("Extraction logs will print out dynamically...")
        main_layout.addWidget(QLabel("<b>Console Output Logs:</b>"))
        main_layout.addWidget(self.log_terminal)

    def sync_weights_ui(self, value):
        """Ensures that checking boundaries sums features to exactly 1.0."""
        ste_val = 1.0 - value
        self.lbl_w_ste.setText(f"<b>{ste_val:.2f}</b>")

    def log(self, msg):
        self.log_terminal.append(msg)
        self.log_terminal.ensureCursorVisible()

    def execute_training_thread(self):
        """Spawns the background worker to keep the interface responsive."""
        self.btn_run.setEnabled(False)
        self.log_terminal.clear()
        self.progress_bar.setValue(0)
        
        self.log("Initializing t context loops...")

        self.t = QThread()
        self.worker = TrainingWorker(
            templates_per_word=self.sb_templates.value(),
            w_zcr=self.sb_w_zcr.value()
        )
        self.worker.moveToThread(self.t)

        # Connect internal signal routes
        self.t.started.connect(self.worker.start_processing)
        self.worker.progress_update.connect(self.on_worker_progress)
        self.worker.training_finished.connect(self.on_worker_success)
        self.worker.training_failed.connect(self.on_worker_failure)

        self.t.start()

    @Slot(int, str)
    def on_worker_progress(self, percent, update_text):
        self.progress_bar.setValue(percent)
        if update_text:
            self.log(update_text)

    @Slot(float, str)
    def on_worker_success(self, accuracy, final_path):
        self.log("\n✨ <b>Training complete!</b>")
        self.log(f"🎯 <b>Final Model Accuracy: {accuracy:.2f}%</b>")
        self.log(f"💾 C Header exported to: <code>{final_path}</code>")
        self.cleanup_thread()

    @Slot(str)
    def on_worker_failure(self, error_msg):
        self.log(f"\n❌ <b>Pipeline execution failed:</b> {error_msg}")
        self.cleanup_thread()

    def cleanup_thread(self):
        """Safely tears down the t once work is complete."""
        if self.t:
            self.t.quit()
            self.t.wait()
        self.btn_run.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioTrainingStudioGUI()
    window.show()
    sys.exit(app.exec())