import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

from historical_preprocessing import load_and_preprocess_historical_data

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
DEFAULT_DATASET = DATA_DIR / "carbon_scheduling_full_dataset.csv"


def train_model(data_path):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    # Load processed data
    X, y, encoders, metadata = load_and_preprocess_historical_data(data_path)

    # Train-Test Split (for internal validation)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Initialize model
    model = RandomForestRegressor(
        n_estimators=100,
        random_state=42
    )

    # Train
    model.fit(X_train, y_train)

    # Evaluate
    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    print("Model Performance:")
    print("MAE:", round(mae, 3))
    print("R2 Score:", round(r2, 3))

    # Save model and encoders
    joblib.dump(model, MODELS_DIR / "carbon_model.pkl")
    # Save encoder bundle with schema metadata for robust inference alignment.
    joblib.dump(
        {
            "encoders": encoders,
            "categorical_cols": metadata["categorical_cols"],
            "feature_columns": metadata["feature_columns"],
        },
        MODELS_DIR / "encoders.pkl",
    )

    print("Model and encoders saved successfully!")

    return model


if __name__ == "__main__":
    train_model(DEFAULT_DATASET)
