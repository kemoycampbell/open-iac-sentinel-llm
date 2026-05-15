import json
import pandas as pd

LOG_FILE = "../logs/drift_detection_failures.log"

# -----------------------------
# Load failure log
# -----------------------------
rows = []
with open(LOG_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            rows.append(json.loads(line))

df = pd.DataFrame(rows)

# -----------------------------
# Basic sanity
# -----------------------------
print("\n=== Total Failures ===")
print(len(df))

# -----------------------------
# Analysis 1: Failures by model
# -----------------------------
print("\n=== Failures by Model ===")
print(df["model"].value_counts())

# -----------------------------
# Analysis 2: Failures by stage
# -----------------------------
print("\n=== Failures by Stage ===")
print(df["stage"].value_counts())

# -----------------------------
# Analysis 3: Failures by error type
# -----------------------------
print("\n=== Failures by Error Type ===")
print(df["error_type"].value_counts())

# -----------------------------
# Analysis 4: Model × Stage matrix
# -----------------------------
print("\n=== Model × Stage ===")
print(
    df.groupby(["model", "stage"])
      .size()
      .unstack(fill_value=0)
)

# -----------------------------
# Analysis 5: Model × Error Type matrix
# -----------------------------
print("\n=== Model × Error Type ===")
print(
    df.groupby(["model", "error_type"])
      .size()
      .unstack(fill_value=0)
)

# -----------------------------
# Analysis 6: Stage × Error Type
# -----------------------------
print("\n=== Stage × Error Type ===")
print(
    df.groupby(["stage", "error_type"])
      .size()
      .unstack(fill_value=0)
)

# -----------------------------
# Analysis 7: Environment distribution
# -----------------------------
print("\n=== Failures by Environment ===")
print(df["environment"].value_counts())

# which model struggle the most
print("\nWhich model struggles the most?")
print(df["model"].value_counts())


# images
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Create output directory
fig_dir = Path("figures")
fig_dir.mkdir(exist_ok=True)

sns.set_theme(style="whitegrid")

# -----------------------------
# Figure A: Failures by Model
# -----------------------------
plt.figure(figsize=(7, 4))
df["model"].value_counts().plot(kind="bar")
plt.title("Failures by Model")
plt.xlabel("Model")
plt.ylabel("Number of Failures")
plt.tight_layout()
plt.savefig(fig_dir / "failures_by_model.png", dpi=300)
plt.close()

# -----------------------------
# Figure B: Failures by Stage
# -----------------------------
plt.figure(figsize=(7, 4))
df["stage"].value_counts().plot(kind="bar")
plt.title("Failures by Pipeline Stage")
plt.xlabel("Stage")
plt.ylabel("Number of Failures")
plt.tight_layout()
plt.savefig(fig_dir / "failures_by_stage.png", dpi=300)
plt.close()

# -----------------------------
# Figure C: Failures by Error Type
# -----------------------------
plt.figure(figsize=(7, 4))
df["error_type"].value_counts().plot(kind="bar")
plt.title("Failures by Error Type")
plt.xlabel("Error Type")
plt.ylabel("Number of Failures")
plt.tight_layout()
plt.savefig(fig_dir / "failures_by_error_type.png", dpi=300)
plt.close()

# -----------------------------
# Figure D: Model × Stage Heatmap
# -----------------------------
model_stage = (
    df.groupby(["model", "stage"])
      .size()
      .unstack(fill_value=0)
)

plt.figure(figsize=(8, 4))
sns.heatmap(model_stage, annot=True, fmt="d", cmap="Blues")
plt.title("Failures by Model and Pipeline Stage")
plt.xlabel("Stage")
plt.ylabel("Model")
plt.tight_layout()
plt.savefig(fig_dir / "model_stage_heatmap.png", dpi=300)
plt.close()

# -----------------------------
# Figure E: Model × Error Type Heatmap
# -----------------------------
model_error = (
    df.groupby(["model", "error_type"])
      .size()
      .unstack(fill_value=0)
)

plt.figure(figsize=(8, 4))
sns.heatmap(model_error, annot=True, fmt="d", cmap="Reds")
plt.title("Failures by Model and Error Type")
plt.xlabel("Error Type")
plt.ylabel("Model")
plt.tight_layout()
plt.savefig(fig_dir / "model_error_heatmap.png", dpi=300)
plt.close()
