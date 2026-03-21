import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = BASE_DIR / "outputs"


def evaluate_carbon_performance(final_schedule_file):

    df = pd.read_csv(Path(final_schedule_file))

    # ==============================
    # Validate Required Columns
    # ==============================
    required_cols = [
        "Predicted_Carbon_Emission",
        "Optimized_Carbon_Emission"
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"{col} not found in dataset.")

    # ==============================
    # Core Calculations
    # ==============================
    total_before = df["Predicted_Carbon_Emission"].sum()
    total_after = df["Optimized_Carbon_Emission"].sum()

    reduction = total_before - total_after

    # Prevent divide-by-zero
    if total_before > 0:
        reduction_percent = (reduction / total_before) * 100
    else:
        reduction_percent = 0

    avg_reduction_per_task = reduction / len(df) if len(df) > 0 else 0

    # ==============================
    # Logical Consistency Check
    # ==============================
    if total_after > total_before:
        print("⚠ Warning: Optimized carbon is higher than predicted carbon.")
        print("Please verify scheduler logic.")

    # ==============================
    # Display Results
    # ==============================
    print("\n===== Carbon Optimization Performance =====")
    print("Total Predicted Carbon :", round(total_before, 3))
    print("Total Optimized Carbon :", round(total_after, 3))
    print("Total Carbon Reduction :", round(reduction, 3))
    print("Percentage Reduction   :", round(reduction_percent, 2), "%")
    print("Avg Reduction per Task :", round(avg_reduction_per_task, 4))

    # ==============================
    # Decision Distribution
    # ==============================
    if "Decision" in df.columns:
        print("\n===== Decision Distribution =====")
        print(df["Decision"].value_counts())

    # ==============================
    # Save Summary Report
    # ==============================
    summary = pd.DataFrame({
        "Total_Predicted_Carbon": [total_before],
        "Total_Optimized_Carbon": [total_after],
        "Total_Reduction": [reduction],
        "Reduction_Percentage": [reduction_percent],
        "Average_Reduction_Per_Task": [avg_reduction_per_task]
    })

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUTS_DIR / "carbon_evaluation_summary.csv", index=False)

    print("\nEvaluation summary saved as 'carbon_evaluation_summary.csv'")

    return summary


if __name__ == "__main__":
    evaluate_carbon_performance(OUTPUTS_DIR / "final_schedule.csv")
