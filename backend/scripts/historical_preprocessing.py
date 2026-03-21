import pandas as pd
from sklearn.preprocessing import LabelEncoder
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DEFAULT_DATASET = DATA_DIR / "carbon_scheduling_full_dataset.csv"


def load_and_preprocess_historical_data(file_path):
    df = pd.read_csv(Path(file_path))

    target_col = "Carbon_Emission"
    if target_col not in df.columns:
        raise ValueError(f"Required target column '{target_col}' not found in {file_path}")

    # Avoid target leakage from bucket labels and explicit decision label.
    drop_cols = {target_col, "Emission_Category", "Decision"}

    # Normalize known schema alias.
    if "Priority_Status" in df.columns and "Priority" not in df.columns:
        df = df.rename(columns={"Priority_Status": "Priority"})

    feature_cols = [c for c in df.columns if c not in drop_cols]
    X = df[feature_cols].copy()
    y = df[target_col].copy()

    # Categorical columns are inferred from dtype for flexibility.
    categorical_cols = X.select_dtypes(include=["object"]).columns.tolist()

    encoders = {}

    # Encode categorical features
    for col in categorical_cols:
        encoder = LabelEncoder()
        X[col] = encoder.fit_transform(X[col].astype(str))
        encoders[col] = encoder

    metadata = {
        "categorical_cols": categorical_cols,
        "feature_columns": feature_cols,
    }

    return X, y, encoders, metadata


if __name__ == "__main__":
    X, y, encoders, metadata = load_and_preprocess_historical_data(DEFAULT_DATASET)

    print("Features shape:", X.shape)
    print("Target shape:", y.shape)
    print("Categorical columns:", metadata["categorical_cols"])
    print("Sample Features:")
    print(X.head())
