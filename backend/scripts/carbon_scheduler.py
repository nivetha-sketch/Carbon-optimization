import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = BASE_DIR / "outputs"


def generate_advanced_schedule(decision_file):

    df = pd.read_csv(Path(decision_file))

    # Efficiency factors (research-style configurable parameters)
    GREEN_REGION_FACTOR = 0.7      # 30% reduction
    NIGHT_SLOT_FACTOR = 0.8        # 20% reduction

    optimized_emission = []
    final_region = []
    final_region_raw = []
    final_time = []
    final_time_raw = []

    for _, row in df.iterrows():

        base_emission = row["Predicted_Carbon_Emission"]
        decision = row["Decision"]

        # Default values (no change)
        new_emission = base_emission
        region = row["Region"]
        time_slot = row["Time_Slot"]
        region_raw = row.get("Region_Raw", region)
        time_slot_raw = row.get("Time_Slot_Raw", time_slot)

        if decision == "Shift_To_Green_Region_And_Night":
            new_emission = base_emission * GREEN_REGION_FACTOR * NIGHT_SLOT_FACTOR
            region = 0          # Green region
            time_slot = 3       # Night slot
            region_raw = "Green_Region"
            time_slot_raw = "Night"

        elif decision == "Green_Region_Immediate":
            new_emission = base_emission * GREEN_REGION_FACTOR
            region = 0
            region_raw = "Green_Region"

        elif decision == "Execute_Immediately":
            # No carbon change
            new_emission = base_emission

        elif decision == "Schedule_Night_Low_Load":
            new_emission = base_emission * NIGHT_SLOT_FACTOR
            time_slot = 3
            time_slot_raw = "Night"

        optimized_emission.append(new_emission)
        final_region.append(region)
        final_region_raw.append(region_raw)
        final_time.append(time_slot)
        final_time_raw.append(time_slot_raw)

    # Add new columns
    df["Final_Region"] = final_region
    df["Final_Region_Raw"] = final_region_raw
    df["Final_Time_Slot"] = final_time
    df["Final_Time_Slot_Raw"] = final_time_raw
    df["Optimized_Carbon_Emission"] = optimized_emission

    # System-level evaluation
    total_before = df["Predicted_Carbon_Emission"].sum()
    total_after = df["Optimized_Carbon_Emission"].sum()
    total_reduction = total_before - total_after
    reduction_percentage = (total_reduction / total_before) * 100 if total_before != 0 else 0

    print("\n===== Advanced Carbon-Aware Optimization Results =====")
    print("Total Before:", round(total_before, 3))
    print("Total After:", round(total_after, 3))
    print("Total Reduction:", round(total_reduction, 3))
    print("Reduction Percentage:", round(reduction_percentage, 2), "%")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUTS_DIR / "final_schedule.csv", index=False)

    return df


if __name__ == "__main__":
    generate_advanced_schedule(OUTPUTS_DIR / "decision_output.csv")
