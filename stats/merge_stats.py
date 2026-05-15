
import json
import pandas as pd

def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


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




df_success = load_jsonl("../logs/drift_detection.log")
df_failure = load_jsonl("../logs/drift_detection_failures.log")

# Parse timestamps
df_success["timestamp"] = pd.to_datetime(df_success["timestamp"])
df_failure["timestamp"] = pd.to_datetime(df_failure["timestamp"])


def attach_nearest_prior_failure(success_row, failure_df):
    subset = failure_df[
        (failure_df["model"] == success_row["model"]) &
        (failure_df["environment"] == success_row["environment"]) &
        (failure_df["timestamp"] < success_row["timestamp"])
    ]

    if subset.empty:
        return pd.Series({
            "had_prior_failure": False,
            "minutes_since_last_failure": None,
            "prior_failure_stage": None,
            "prior_failure_type": None
        })

    nearest = subset.sort_values("timestamp").iloc[-1]
    delta = (success_row["timestamp"] - nearest["timestamp"]).total_seconds() / 60

    return pd.Series({
        "had_prior_failure": True,
        "minutes_since_last_failure": delta,
        "prior_failure_stage": nearest["stage"],
        "prior_failure_type": nearest["error_type"]
    })


df_success = pd.concat(
    [
        df_success,
        df_success.apply(
            lambda row: attach_nearest_prior_failure(row, df_failure),
            axis=1
        )
    ],
    axis=1
)


print("\n=== Successes with Prior Failure Context ===")
print("has prior failure value counts:")
print(df_success["had_prior_failure"].value_counts())


df_success["locality_consistent"] = df_success.apply(
    lambda row: (
        locality_context_is_valid(row.get("patch_context"))
        and row.get("refresh_clean") is True
    ),
    axis=1
)


print(f"Local consistency after failure {df_success.groupby('had_prior_failure')['locality_consistent'].mean()}")

print(f"Failure by model{df_success.groupby(['model', 'had_prior_failure'])['locality_consistent'].mean()}")