import pandas as pd
import joblib
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR = BASE_DIR / "outputs"


def _safe_label_transform(series, encoder):
    value_to_idx = {v: i for i, v in enumerate(encoder.classes_)}
    fallback = 0
    return series.astype(str).map(lambda x: value_to_idx.get(x, fallback))


def predict_new_workload(new_data_path):
    # Load trained model
    model = joblib.load(MODELS_DIR / "carbon_model.pkl")

    # Load saved encoder bundle (new format) or fallback to old format.
    encoder_bundle = joblib.load(MODELS_DIR / "encoders.pkl")
    if isinstance(encoder_bundle, dict) and "encoders" in encoder_bundle:
        encoders = encoder_bundle["encoders"]
        categorical_cols = encoder_bundle.get("categorical_cols", list(encoders.keys()))
        feature_columns = encoder_bundle.get("feature_columns")
    else:
        encoders = encoder_bundle
        categorical_cols = list(encoders.keys())
        feature_columns = None

    # Load new workload dataset
    df_raw = pd.read_csv(Path(new_data_path))
    df = df_raw.copy()

    # Preserve human-readable columns for decision layer and UI.
    if "Priority_Status" in df_raw.columns:
        df["Priority_Status_Raw"] = df_raw["Priority_Status"]
        # Align inference input with trained feature name if needed.
        if "Priority" not in df.columns:
            df["Priority"] = df_raw["Priority_Status"]
    if "Priority" in df_raw.columns:
        df["Priority_Raw"] = df_raw["Priority"]
    if "Region" in df_raw.columns:
        df["Region_Raw"] = df_raw["Region"]
    if "Time_Slot" in df_raw.columns:
        df["Time_Slot_Raw"] = df_raw["Time_Slot"]

    # Apply SAME encoders (DO NOT fit again)
    for col in categorical_cols:
        if col in df.columns and col in encoders:
            df[col] = _safe_label_transform(df[col], encoders[col])

    if feature_columns:
        missing_cols = [c for c in feature_columns if c not in df.columns]
        for col in missing_cols:
            df[col] = 0
        model_input = df[feature_columns]
    else:
        model_input = df

    # Predict carbon emission
    predictions = model.predict(model_input)

    # Add predictions to dataframe
    df["Predicted_Carbon_Emission"] = predictions

    # Save results
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUTS_DIR / "predicted_workload_output.csv", index=False)

    print("Prediction completed successfully!")
    print(df.head())

    return df


if __name__ == "__main__":
    predict_new_workload(DATA_DIR / "new_incoming_workload.csv")
