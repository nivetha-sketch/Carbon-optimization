import pandas as pd
import numpy as np
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = BASE_DIR / "outputs"


def apply_advanced_decision_logic(predicted_file):

    df = pd.read_csv(Path(predicted_file))

    # Dynamic threshold (Top 25%)
    high_carbon_threshold = np.percentile(
        df["Predicted_Carbon_Emission"], 75
    )

    decisions = []

    for _, row in df.iterrows():

        carbon = row["Predicted_Carbon_Emission"]
        priority_raw = str(row.get("Priority_Status_Raw", row.get("Priority_Raw", ""))).strip().lower()
        is_urgent = priority_raw in {"high", "critical"}

        if carbon >= high_carbon_threshold and not is_urgent:
            decisions.append("Shift_To_Green_Region_And_Night")

        elif carbon >= high_carbon_threshold and is_urgent:
            decisions.append("Green_Region_Immediate")

        elif is_urgent:
            decisions.append("Execute_Immediately")

        else:
            decisions.append("Schedule_Night_Low_Load")

    df["Decision"] = decisions
    print("\n===== Decision Summary =====")
    print(df["Decision"].value_counts())

    print("\nSample Decisions:")
    sample_cols = [c for c in ["Predicted_Carbon_Emission", "Priority_Status_Raw", "Priority_Raw", "Decision"] if c in df.columns]
    print(df[sample_cols].head())

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUTS_DIR / "decision_output.csv", index=False)
    print("\nAdvanced Decision Logic Applied")
    print("High Carbon Threshold:", round(high_carbon_threshold, 3))
    return df


if __name__ == "__main__":
    apply_advanced_decision_logic(OUTPUTS_DIR / "predicted_workload_output.csv")
