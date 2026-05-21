import os
import numpy as np
import librosa
from sklearn.model_selection import train_test_split
from sklearn.cluster import KMeans
import wave

ROOT = "."

SAMPLE_PATH = f"{ROOT}/Samples/" 
if not os.path.exists(SAMPLE_PATH):
    raise FileNotFoundError(f"The directory '{SAMPLE_PATH}' does not exist.")

EXPORT_PATH = f"{ROOT}/exported_templates/"
os.makedirs(EXPORT_PATH, exist_ok=True)

TEMPLATES_PER_WORD = 4
W_ZCR = 0.6
W_STE = 1.0 - W_ZCR

# Dynamically generate the WORDS list from folder names
WORDS = sorted([
    d for d in os.listdir(SAMPLE_PATH) 
    if os.path.isdir(os.path.join(SAMPLE_PATH, d)) and not d.startswith('.')
])

print(f"Detected {len(WORDS)} words dynamically: {WORDS}")

def extract_zcr_ste(filepath, target_sr=8000, duration=1.0, frame_size=128, hop_size=128):
    y, sr = librosa.load(filepath, sr=target_sr, mono=True)

    N_FEATURES = 99
    TOTAL_SAMPLES = frame_size * N_FEATURES  # 99 frames of 128 samples each = 12,672 samples (~1.58 seconds)

    if len(y) < TOTAL_SAMPLES:
        print(f"Warning: '{os.path.basename(filepath)}' is shorter than {duration} seconds. Padding with zeros.")
        y_fixed = np.pad(y, (0, TOTAL_SAMPLES - len(y)))
    else:
        y_fixed = y[:TOTAL_SAMPLES]

    # Pre-emphasis Filter
    y_fixed = librosa.effects.preemphasis(y_fixed, coef=0.95)
    y_fixed = y_fixed / 1.95  # Normalize to keep energy consistent after pre-emphasis
    
    frames = librosa.util.frame(y_fixed, frame_length=frame_size, hop_length=hop_size)

    zcr = librosa.feature.zero_crossing_rate(y_fixed, frame_length=frame_size, hop_length=hop_size, center=False)[0]
    ste = np.mean(frames**2, axis=0)

    zcr = zcr[:N_FEATURES]
    ste = ste[:N_FEATURES]

    # zcr = zcr / np.max(zcr) if np.max(zcr) > 0 else zcr
    # ste = ste / np.max(ste) if np.max(ste) > 0 else ste

    return zcr, ste

## Load Data and Extract Features
X_zcr, X_ste, Y = [], [], []

print("\nExtracting perfectly centered, smoothed, AND pre-emphasized features...")
for word_idx, word_name in enumerate(WORDS):
    word_dir = os.path.join(SAMPLE_PATH, word_name)

    for sample in os.listdir(word_dir):
        if sample.endswith('.wav'):
            filepath = os.path.join(word_dir, sample)
            try:
                zcr, ste = extract_zcr_ste(filepath)
                X_zcr.append(zcr)
                X_ste.append(ste)
                Y.append(word_idx)
            except Exception as e:
                print(f"Error processing {sample}: {e}")

X_zcr = np.array(X_zcr)
X_ste = np.array(X_ste)
Y = np.array(Y)
print(f"Total samples loaded: {len(Y)}")

if len(Y) == 0:
    raise ValueError("No data loaded. Check your wav files are placed correctly.")

# Split 80% Train, 20% Test
X_zcr_train, X_zcr_test, X_ste_train, X_ste_test, Y_train, Y_test = train_test_split(
    X_zcr, X_ste, Y, test_size=0.20, random_state=42, stratify=Y
)

print(f"Generating {TEMPLATES_PER_WORD} templates per word...")

zcr_templates = []
ste_templates = []
template_labels = []

for i in range(len(WORDS)):
    class_zcr = np.array(X_zcr_train[Y_train == i])
    class_ste = np.array(X_ste_train[Y_train == i])

    if len(class_zcr) < TEMPLATES_PER_WORD:
        print(f"Warning: Not enough samples for '{WORDS[i]}' to generate templates. Skipping.")
        continue

    # Combine features
    combined_features = np.hstack((class_zcr * W_ZCR, class_ste * W_STE))

    kmeans = KMeans(n_clusters=TEMPLATES_PER_WORD, random_state=42, n_init=10)
    kmeans.fit(combined_features)

    for k in range(TEMPLATES_PER_WORD):
        center = kmeans.cluster_centers_[k]

        # Use Manhattan distance
        distances = np.sum(np.abs(combined_features - center), axis=1)
        best_idx = np.argmin(distances)

        zcr_templates.append(class_zcr[best_idx])
        ste_templates.append(class_ste[best_idx])
        template_labels.append(i)

zcr_templates = np.array(zcr_templates)
ste_templates = np.array(ste_templates)
template_labels = np.array(template_labels)

## Testing Step
correct_predictions = 0
total_predictions = len(Y_test)

print("--- Testing on Unseen Data (Multi-Template Manhattan) ---")
for i in range(total_predictions):
    test_zcr = X_zcr_test[i]
    test_ste = X_ste_test[i]
    true_label = Y_test[i]

    distances_zcr = np.sum(np.abs(zcr_templates - test_zcr), axis=1)
    distances_ste = np.sum(np.abs(ste_templates - test_ste), axis=1)

    total_distances = (W_ZCR * distances_zcr) + (W_STE * distances_ste)
    predicted_index = total_distances.argmin()
    predicted_label = template_labels[predicted_index]

    if predicted_label == true_label:
        correct_predictions += 1

accuracy = (correct_predictions / total_predictions) * 100
print(f"Final Testing Accuracy: {accuracy:.2f}% ({correct_predictions}/{total_predictions} correct)")

# Export to C Format
header_path = os.path.join(EXPORT_PATH, "word_templates.h")
num_templates = len(template_labels)
num_frames = zcr_templates.shape[1]

with open(header_path, "w", encoding="utf-8") as f:
    f.write("#ifndef WORD_TEMPLATES_H\n")
    f.write("#define WORD_TEMPLATES_H\n\n")
    f.write("#include <stdint.h>\n\n")
    f.write(f"#define N_WORDS {len(WORDS)}\n")
    f.write(f"#define TEMPLATES_PER_WORD {TEMPLATES_PER_WORD}\n")
    f.write(f"#define TOTAL_TEMPLATES {num_templates}\n")
    f.write(f"#define N_FEATURES {num_frames}\n\n")

    f.write(f"const float W_STE = {W_STE}f;\n")
    f.write(f"const float W_ZCR = {W_ZCR}f;\n\n")

    f.write("static const char* words[] = {\n    ")
    f.write(", ".join([f'"{w}"' for w in WORDS]))
    f.write("\n};\n\n")

    # Mapping tracker array
    f.write("const uint8_t template_labels[TOTAL_TEMPLATES] PROGMEM = {\n    ")
    f.write(", ".join([str(lbl) for lbl in template_labels]))
    f.write("\n};\n\n")

    # Export ZCR Matrix
    f.write("const float zcr_templates[TOTAL_TEMPLATES][N_FEATURES] PROGMEM = {\n")
    for i in range(num_templates):
        word_name = WORDS[template_labels[i]]
        f.write(f"    // Template {i} - Word: {word_name}\n    {{")
        f.write(", ".join([f"{val:.4f}" for val in zcr_templates[i]]))
        f.write("},\n")
    f.write("};\n\n")

    # Export STE Matrix
    f.write("const float ste_templates[TOTAL_TEMPLATES][N_FEATURES] PROGMEM = {\n")
    for i in range(num_templates):
        word_name = WORDS[template_labels[i]]
        f.write(f"    // Template {i} - Word: {word_name}\n    {{")
        f.write(", ".join([f"{val:.4f}" for val in ste_templates[i]]))
        f.write("},\n")
    f.write("};\n\n")

    f.write("#endif // WORD_TEMPLATES_H\n")

print(f"C header saved to: {header_path}")