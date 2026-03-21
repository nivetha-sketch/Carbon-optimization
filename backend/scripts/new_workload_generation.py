import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

np.random.seed(100)

n = 100  # New incoming tasks

task_types = [
    "Fleet Dispatch",
    "Order Processing",
    "Payment Settlement",
    "Inventory Update",
    "Customer Analytics",
    "API Gateway",
    "Fraud Detection",
    "Data Sync",
]

workload_levels = ["Low", "Medium", "High", "Critical"]
resource_types = [
    "VM_Micro",
    "VM_Small",
    "VM_Medium",
    "VM_Large",
    "VM_XLarge",
    "Container_Small",
    "Container_Micro",
]
priorities = ["Low", "Medium", "High", "Critical"]
regions = ["us-east", "us-west", "eu-central", "ap-south", "ap-east"]
time_slots = ["Peak", "Off-Peak", "Night", "Weekend"]

data = {
    "Task_Type": np.random.choice(task_types, n),
    "Workload_Level": np.random.choice(workload_levels, n),
    "Execution_Time": np.random.randint(5, 320, n),
    "Resource_Type": np.random.choice(resource_types, n),
    "Priority_Status": np.random.choice(priorities, n),
    "Energy_Consumption": np.round(np.random.uniform(0.15, 9.5, n), 2),
    "Region": np.random.choice(regions, n),
    "Time_Slot": np.random.choice(time_slots, n),
}

df = pd.DataFrame(data)

DATA_DIR.mkdir(parents=True, exist_ok=True)
df.to_csv(DATA_DIR / "new_incoming_workload.csv", index=False)

print("New workload dataset generated successfully!")
print("Dataset Shape:", df.shape)
print(df.head())
