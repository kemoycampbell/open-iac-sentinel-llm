import json
import pandas as pd

LOG_FILE = "../logs/drift_detection.log"

# -----------------------------
# Load drift_detection.log
# -----------------------------
rows = []
with open(LOG_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            rows.append(json.loads(line))

df = pd.DataFrame(rows)

# -----------------------------
# Extract explicit fields
# -----------------------------
df["expected_method"] = df["correct_method"]
df["chosen_method"] = df["opensentinel_method"]
df["method_match"] = df["expected_method"] == df["chosen_method"]
df["refresh_used"] = df["chosen_method"] == "terraform_refresh"
df["refresh_succeeded"] = df["refresh_clean"] == True

# Extract change_area.method safely
df["change_area_method"] = df["patch_context"].apply(
    lambda x: x.get("change_area", {}).get("method") if isinstance(x, dict) else None
)

# -----------------------------
# Analysis 1: Overall counts
# -----------------------------
print("\n=== Total Drift Events ===")
print(len(df))

print("\n=== Method Match vs Mismatch ===")
print(df["method_match"].value_counts())

print("\n=== Refresh Usage ===")
print(df["refresh_used"].value_counts())

print("\n=== Refresh Success ===")
print(df["refresh_succeeded"].value_counts())

# -----------------------------
# Analysis 2: By model
# -----------------------------
print("\n=== Method Match by Model ===")
print(
    df.groupby(["model", "method_match"])
      .size()
      .unstack(fill_value=0)
)

print("\n=== Refresh Used by Model ===")
print(
    df.groupby(["model", "refresh_used"])
      .size()
      .unstack(fill_value=0)
)

# -----------------------------
# Analysis 3: By environment
# -----------------------------
print("\n=== Method Match by Environment ===")
print(
    df.groupby(["environment", "method_match"])
      .size()
      .unstack(fill_value=0)
)

# -----------------------------
# Analysis 4: By change_area.method
# -----------------------------
print("\n=== Method Match by Change Area Method ===")
print(
    df.groupby(["change_area_method", "method_match"])
      .size()
      .unstack(fill_value=0)
)

# -----------------------------
# Analysis 5: Attribute-level view
# -----------------------------
print("\n=== Attribute vs Chosen Method ===")
print(
    df.groupby(["attribute", "chosen_method"])
      .size()
      .unstack(fill_value=0)
)

# -----------------------------
# Analysis 6: Resource-level view
# -----------------------------
print("\n=== Resource vs Chosen Method ===")
print(
    df.groupby(["resource", "chosen_method"])
      .size()
      .unstack(fill_value=0)
)

# -----------------------------
# Derived ratios (still factual)
# -----------------------------
total = len(df)
refresh_ratio = df["refresh_used"].sum() / total


print("\n=== Ratios ===")
print(f"Refresh usage ratio: {refresh_ratio:.2%}")


#locality stats


def locality_context_is_valid(patch_context):
    if not isinstance(patch_context, dict):
        return False

    ca = patch_context.get("change_area")
    if not isinstance(ca, dict):
        return False

    if ca.get("method") not in {
        "resource_attribute_update",
        "variable_update"
    }:
        return False

    if not isinstance(ca.get("defined_in"), str):
        return False

    if ca.get("source") not in {"resource", "tfvars", "default"}:
        return False

    return True


df["locality_consistent"] = df.apply(
    lambda row: (
        locality_context_is_valid(row["patch_context"])
        and row["refresh_clean"] is True
    ),
    axis=1
)
print("\n=== Locality Consistent ===")
print(df["locality_consistent"].value_counts())



import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

sns.set_theme(style="whitegrid")

# Create output directory
fig_dir = Path("figures")
fig_dir.mkdir(exist_ok=True)

# Count locality consistency
counts = df["locality_consistent"].value_counts()

plt.figure(figsize=(5, 4))
counts.plot(kind="bar", color=["#4CAF50", "#F44336"])
plt.title("Locality Consistency of Drift Remediation")
plt.xlabel("Locality Consistent")
plt.ylabel("Number of Drift Events")
plt.xticks(rotation=0)
plt.tight_layout()
plt.savefig(fig_dir / "locality_consistency.png", dpi=300)
plt.close()



by_resource = (
    df.groupby("resource")["locality_consistent"]
      .mean()
      .sort_values(ascending=False)
)



plt.figure(figsize=(10, 6))
by_resource.sort_values().plot(
    kind="barh",
    color="#2ca02c"
)
plt.xlim(0, 1)
plt.title("Locality Consistency by Resource")
plt.xlabel("Locality Consistency Ratio")
plt.ylabel("Resource")
plt.tight_layout()
plt.savefig(fig_dir / "locality_consistency_by_resource.png", dpi=300)
plt.close()




# -----------------------------
# Locality consistency by model
# -----------------------------
print("\n=== Locality Consistency by Model ===")
print(
    df.groupby("model")["locality_consistent"]
      .agg(
          total_events="count",
          locality_success="sum",
          locality_ratio="mean"
      )
      .sort_values("locality_ratio", ascending=False)
)


# -----------------------------
# Plot: Locality consistency by model
# -----------------------------

VALID_MODELS = {
    "gpt-oss:20b",
    "qwen3-coder:latest"
}

df_consistent = df[df["model"].isin(VALID_MODELS)]

# -----------------------------
# Plot: Locality consistency by model (filtered)
# -----------------------------
by_model = (
    df_consistent.groupby("model")["locality_consistent"]
      .mean()
      .sort_values(ascending=False)
)

plt.figure(figsize=(6, 4))
by_model.plot(kind="bar", color="#1f77b4")
plt.ylim(0, 1)
plt.title("Locality Consistency by Model")
plt.xlabel("Model")
plt.ylabel("Locality Consistency Ratio")
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
plt.savefig(fig_dir / "locality_consistency_by_model.png", dpi=300)
plt.close()


