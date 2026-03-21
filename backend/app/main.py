from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Literal
import json
from uuid import uuid4

import pandas as pd
import joblib
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_ROOT / "scripts"
OUTPUTS_DIR = BACKEND_ROOT / "outputs"
DATA_DIR = BACKEND_ROOT / "data"
MODELS_DIR = BACKEND_ROOT / "models"
ALERT_RULES_PATH = OUTPUTS_DIR / "alert_rules.json"
UPLOADED_WORKLOAD_PATH = DATA_DIR / "new_incoming_workload.csv"

PIPELINE_SCRIPTS = {
    "train": "model_training.py",
    "generate": "new_workload_generation.py",
    "predict": "prediction_module.py",
    "decide": "carbon_decision_module.py",
    "schedule": "carbon_scheduler.py",
    "evaluate": "carbon_evaluation.py",
    "coverage": "regenerate_outputs_coverage.py",
}
TRAINING_DATASET = "data/carbon_scheduling_full_dataset.csv"

DECISION_LABELS = {
    "Execute_Immediately": "Execute Immediately",
    "Shift_To_Green_Region_And_Night": "Shift to Green Region + Night",
    "Green_Region_Immediate": "Green Region Immediate",
    "Schedule_Night_Low_Load": "Schedule Night (Low Load)",
}
class FilterPayload(BaseModel):
    decisions: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    priorities: list[str] = Field(default_factory=list)
    logic: Literal["and"] = "and"
    limit: int = 300


class AlertRule(BaseModel):
    id: str | None = None
    name: str
    metric: str = "Reduction_Percentage"
    operator: Literal["lt", "lte", "gt", "gte"] = "lt"
    threshold: float
    enabled: bool = True


class AlertRulesPayload(BaseModel):
    rules: list[AlertRule]


app = FastAPI(title="Carbon Scheduler API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def read_csv_safe(name: str) -> pd.DataFrame:
    path = OUTPUTS_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{path.name} not found in outputs. Run pipeline first.")
    return pd.read_csv(path)


def normalized_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def apply_filters(df: pd.DataFrame, payload: FilterPayload) -> pd.DataFrame:
    if not (payload.decisions or payload.regions or payload.priorities):
        return df.copy()
    mask = pd.Series(True, index=df.index)

    if payload.decisions and "Decision" in df.columns:
        cond = df["Decision"].astype(str).isin([str(x) for x in payload.decisions])
        mask = mask & cond
    if payload.regions:
        if "Final_Region_Raw" in df.columns:
            cond = df["Final_Region_Raw"].astype(str).isin([str(x) for x in payload.regions])
        elif "Region_Raw" in df.columns:
            cond = df["Region_Raw"].astype(str).isin([str(x) for x in payload.regions])
        elif "Final_Region" in df.columns:
            cond = df["Final_Region"].astype(str).isin([str(x) for x in payload.regions])
        else:
            cond = pd.Series(True, index=df.index)
        mask = mask & cond
    if payload.priorities:
        if "Priority_Status_Raw" in df.columns:
            cond = df["Priority_Status_Raw"].astype(str).isin([str(x) for x in payload.priorities])
        elif "Priority_Raw" in df.columns:
            cond = df["Priority_Raw"].astype(str).isin([str(x) for x in payload.priorities])
        elif "Priority" in df.columns:
            cond = df["Priority"].astype(str).isin([str(x) for x in payload.priorities])
        else:
            cond = pd.Series(True, index=df.index)
        mask = mask & cond

    return df[mask].copy()


def compute_analytics(payload: FilterPayload) -> dict:
    df = read_csv_safe("final_schedule.csv")
    filtered = apply_filters(df, payload)

    if filtered.empty:
        return {
            "counts": {"total": len(df), "filtered": 0},
            "insights": [],
            "charts": {"decisionMix": [], "regionMix": [], "carbonByDecision": [], "trend": [], "carbonByRegion": []},
            "table": [],
        }

    pretty = filtered.copy()
    if "Decision" in pretty.columns:
        pretty["Decision_Label"] = pretty["Decision"].map(DECISION_LABELS).fillna(pretty["Decision"])
    if "Final_Region_Raw" in pretty.columns:
        pretty["Region_Label"] = pretty["Final_Region_Raw"].astype(str)
    elif "Region_Raw" in pretty.columns:
        pretty["Region_Label"] = pretty["Region_Raw"].astype(str)
    elif "Final_Region" in pretty.columns:
        pretty["Region_Label"] = pretty["Final_Region"].astype(str)
    if "Priority_Status_Raw" in pretty.columns:
        pretty["Priority_Label"] = pretty["Priority_Status_Raw"].astype(str)
    elif "Priority_Raw" in pretty.columns:
        pretty["Priority_Label"] = pretty["Priority_Raw"].astype(str)
    elif "Priority" in pretty.columns:
        pretty["Priority_Label"] = pretty["Priority"].astype(str)

    total_pred = float(pretty["Predicted_Carbon_Emission"].sum()) if "Predicted_Carbon_Emission" in pretty.columns else 0.0
    total_opt = float(pretty["Optimized_Carbon_Emission"].sum()) if "Optimized_Carbon_Emission" in pretty.columns else 0.0
    cut = total_pred - total_opt
    cut_pct = (cut / total_pred * 100) if total_pred else 0.0

    decision_mix = []
    if "Decision_Label" in pretty.columns:
        decision_counts = pretty["Decision_Label"].value_counts().reset_index()
        decision_counts.columns = ["name", "count"]
        decision_mix = decision_counts.to_dict(orient="records")

    region_mix = []
    if "Region_Label" in pretty.columns:
        region_counts = pretty["Region_Label"].value_counts().reset_index()
        region_counts.columns = ["name", "count"]
        region_mix = region_counts.to_dict(orient="records")
    carbon_by_decision = (
        pretty.groupby("Decision_Label")
        .agg(predicted=("Predicted_Carbon_Emission", "sum"), optimized=("Optimized_Carbon_Emission", "sum"))
        .reset_index()
        .rename(columns={"Decision_Label": "name"})
        .to_dict(orient="records")
        if {"Decision_Label", "Predicted_Carbon_Emission", "Optimized_Carbon_Emission"}.issubset(pretty.columns)
        else []
    )
    trend = (
        pretty[["Predicted_Carbon_Emission", "Optimized_Carbon_Emission"]]
        .head(100)
        .reset_index()
        .rename(columns={"index": "task"})
        .to_dict(orient="records")
        if {"Predicted_Carbon_Emission", "Optimized_Carbon_Emission"}.issubset(pretty.columns)
        else []
    )
    carbon_by_region = (
        pretty.groupby("Region_Label")["Optimized_Carbon_Emission"]
        .sum()
        .reset_index()
        .rename(columns={"Region_Label": "name", "Optimized_Carbon_Emission": "optimized"})
        .to_dict(orient="records")
        if {"Region_Label", "Optimized_Carbon_Emission"}.issubset(pretty.columns)
        else []
    )

    insights = [
        {"title": "Net Carbon Reduction", "value": f"{cut:,.2f}", "description": f"{cut_pct:.1f}% lower emissions for current filters."},
        {"title": "Matched Tasks", "value": str(len(pretty)), "description": f"Out of {len(df)} total tasks."},
    ]
    if "Decision_Label" in pretty.columns:
        top_decision = pretty["Decision_Label"].value_counts().idxmax()
        insights.append({"title": "Most Common Decision", "value": top_decision, "description": "Highest-frequency strategy in filtered view."})

    table = pretty.head(max(1, min(payload.limit, 1000))).to_dict(orient="records")

    return {
        "counts": {"total": len(df), "filtered": len(pretty)},
        "insights": insights,
        "charts": {
            "decisionMix": decision_mix,
            "regionMix": region_mix,
            "carbonByDecision": carbon_by_decision,
            "trend": trend,
            "carbonByRegion": carbon_by_region,
        },
        "table": table,
    }


def run_script(script_name: str) -> tuple[bool, str]:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return False, f"Script not found: {script_name}"

    cmd = [sys.executable, str(script_path)]
    try:
        res = subprocess.run(
            cmd,
            cwd=str(BACKEND_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        output = (res.stdout or "") + (res.stderr or "")
        return res.returncode == 0, output.strip() or "(no output)"
    except Exception as exc:
        return False, str(exc)


def default_alert_rules() -> list[dict]:
    return [
        {
            "id": str(uuid4()),
            "name": "Reduction percentage below target",
            "metric": "Reduction_Percentage",
            "operator": "lt",
            "threshold": 20.0,
            "enabled": True,
        }
    ]


def load_alert_rules() -> list[dict]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    if not ALERT_RULES_PATH.exists():
        rules = default_alert_rules()
        ALERT_RULES_PATH.write_text(json.dumps({"rules": rules}, indent=2), encoding="utf-8")
        return rules
    try:
        raw = json.loads(ALERT_RULES_PATH.read_text(encoding="utf-8"))
        return raw.get("rules", [])
    except Exception:
        rules = default_alert_rules()
        ALERT_RULES_PATH.write_text(json.dumps({"rules": rules}, indent=2), encoding="utf-8")
        return rules


def compare_metric(value: float, operator: str, threshold: float) -> bool:
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    return False


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/pipeline/run/{step}")
def run_pipeline(step: str, mode: Literal["demo", "real"] = "demo") -> dict:
    if step == "all":
        logs: list[dict] = []
        if mode == "real":
            sequence = ["train", "predict", "decide", "schedule", "evaluate"]
        else:
            sequence = ["train", "generate", "predict", "decide", "schedule", "evaluate", "coverage"]
        for key in sequence:
            ok, out = run_script(PIPELINE_SCRIPTS[key])
            logs.append({"step": key, "success": ok, "output": out})
            if not ok:
                return {"success": False, "logs": logs}
        return {"success": True, "mode": mode, "logs": logs}

    if step not in PIPELINE_SCRIPTS:
        raise HTTPException(status_code=400, detail="Invalid step")

    ok, out = run_script(PIPELINE_SCRIPTS[step])
    return {"success": ok, "step": step, "output": out}


@app.post("/pipeline/upload-workload")
async def upload_workload(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    temp_path = DATA_DIR / f"__upload_temp_{uuid4()}.csv"
    temp_path.write_bytes(content)
    try:
        df = pd.read_csv(temp_path)
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}") from exc

    model_meta = None
    enc_path = MODELS_DIR / "encoders.pkl"
    if enc_path.exists():
        try:
            bundle = joblib.load(enc_path)
            if isinstance(bundle, dict):
                model_meta = bundle
        except Exception:
            model_meta = None

    required_cols = []
    if model_meta and model_meta.get("feature_columns"):
        required_cols = list(model_meta["feature_columns"])
    else:
        required_cols = [
            "Task_Type",
            "Workload_Level",
            "Execution_Time",
            "Resource_Type",
            "Priority",
            "Energy_Consumption",
            "Region",
            "Time_Slot",
        ]

    alias_map = {
        "Priority": ["Priority_Status"],
    }

    missing = []
    for col in required_cols:
        if col in df.columns:
            continue
        aliases = alias_map.get(col, [])
        if any(a in df.columns for a in aliases):
            continue
        missing.append(col)

    if missing:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded CSV is missing required columns for inference: {missing}",
        )

    temp_path.replace(UPLOADED_WORKLOAD_PATH)
    return {
        "success": True,
        "message": "Workload uploaded and validated successfully.",
        "saved_to": str(UPLOADED_WORKLOAD_PATH),
        "rows": len(df),
        "columns": df.columns.tolist(),
    }


@app.get("/model/config")
def model_config() -> dict:
    return {
        "training_dataset": TRAINING_DATASET,
        "steps": list(PIPELINE_SCRIPTS.keys()),
    }


@app.get("/alerts/rules")
def get_alert_rules() -> dict:
    return {"rules": load_alert_rules()}


@app.post("/alerts/rules")
def save_alert_rules(payload: AlertRulesPayload) -> dict:
    rules = []
    for r in payload.rules:
        row = r.model_dump()
        if not row.get("id"):
            row["id"] = str(uuid4())
        rules.append(row)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    ALERT_RULES_PATH.write_text(json.dumps({"rules": rules}, indent=2), encoding="utf-8")
    return {"success": True, "rules": rules}


@app.get("/alerts/evaluate")
def evaluate_alerts() -> dict:
    summary = read_csv_safe("carbon_evaluation_summary.csv")
    kpis = summary.iloc[0].to_dict() if not summary.empty else {}
    rules = load_alert_rules()
    triggered = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        metric = rule.get("metric")
        if metric not in kpis:
            continue
        current = float(kpis.get(metric, 0))
        threshold = float(rule.get("threshold", 0))
        op = str(rule.get("operator", "lt"))
        if compare_metric(current, op, threshold):
            triggered.append(
                {
                    "id": rule.get("id"),
                    "name": rule.get("name"),
                    "metric": metric,
                    "operator": op,
                    "threshold": threshold,
                    "current": current,
                }
            )
    return {"kpis": kpis, "rules": rules, "triggered": triggered}


@app.get("/dashboard/meta")
def dashboard_meta() -> dict:
    df = read_csv_safe("final_schedule.csv")
    summary = read_csv_safe("carbon_evaluation_summary.csv")
    row = summary.iloc[0].to_dict() if not summary.empty else {}

    decisions = sorted(df["Decision"].dropna().astype(str).unique().tolist()) if "Decision" in df.columns else []
    if "Final_Region_Raw" in df.columns:
        regions = sorted(df["Final_Region_Raw"].dropna().astype(str).unique().tolist())
    elif "Region_Raw" in df.columns:
        regions = sorted(df["Region_Raw"].dropna().astype(str).unique().tolist())
    else:
        regions = sorted(df["Final_Region"].dropna().astype(str).unique().tolist()) if "Final_Region" in df.columns else []

    if "Priority_Status_Raw" in df.columns:
        priorities = sorted(df["Priority_Status_Raw"].dropna().astype(str).unique().tolist())
    elif "Priority_Raw" in df.columns:
        priorities = sorted(df["Priority_Raw"].dropna().astype(str).unique().tolist())
    else:
        priorities = sorted(df["Priority"].dropna().astype(str).unique().tolist()) if "Priority" in df.columns else []

    return {
        "kpis": row,
        "filters": {
            "decisions": [{"value": d, "label": DECISION_LABELS.get(d, d)} for d in decisions],
            "regions": [{"value": r, "label": str(r)} for r in regions],
            "priorities": [{"value": p, "label": str(p)} for p in priorities],
        },
    }


@app.post("/dashboard/analytics")
def dashboard_analytics(payload: FilterPayload) -> dict:
    return compute_analytics(payload)


@app.post("/dashboard/explain")
def dashboard_explain(payload: FilterPayload) -> dict:
    analytics = compute_analytics(payload)
    filtered = analytics["counts"]["filtered"]
    total = analytics["counts"]["total"]
    if filtered == 0:
        return {
            "summary": "No tasks match the current filters, so explainability insights are unavailable.",
            "drivers": [],
            "recommendations": ["Clear one or more filters.", "Start with only one filter and narrow gradually."],
            "risk_level": "high",
        }

    cut_insight = next((x for x in analytics["insights"] if x["title"] == "Net Carbon Reduction"), None)
    top_decision = next((x for x in analytics["insights"] if x["title"] == "Most Common Decision"), None)
    cut_value = cut_insight["value"] if cut_insight else "0.00"
    cut_desc = cut_insight["description"] if cut_insight else "No reduction data."
    top_decision_value = top_decision["value"] if top_decision else "N/A"
    share_pct = round((filtered / total) * 100, 1) if total else 0

    decision_delta = []
    for row in analytics["charts"]["carbonByDecision"]:
        predicted = float(row.get("predicted", 0))
        optimized = float(row.get("optimized", 0))
        saved = predicted - optimized
        pct = (saved / predicted * 100) if predicted else 0
        decision_delta.append({"decision": row.get("name", "Unknown"), "saved": saved, "pct": pct})
    decision_delta.sort(key=lambda x: x["saved"], reverse=True)
    best_driver = decision_delta[0] if decision_delta else None

    risk_level = "low"
    if share_pct < 20:
        risk_level = "high"
    elif share_pct < 50:
        risk_level = "medium"

    drivers = []
    if best_driver:
        drivers.append(
            f"Strongest reduction driver: {best_driver['decision']} with {best_driver['saved']:.2f} units saved ({best_driver['pct']:.1f}%)."
        )
    drivers.append(f"Current filters cover {filtered} of {total} tasks ({share_pct}%).")
    drivers.append(f"Most frequent strategy in view: {top_decision_value}.")

    recommendations = [
        "Prioritize strategies with higher saved carbon in high-volume regions.",
        "Use Decision + Region filters to compare before/after carbon for operational planning.",
    ]
    if risk_level == "high":
        recommendations.append("Widen filters to improve confidence; current segment is too narrow for strong conclusions.")

    return {
        "summary": f"Filtered workload reduces carbon by {cut_value} ({cut_desc}).",
        "drivers": drivers,
        "recommendations": recommendations,
        "risk_level": risk_level,
    }
