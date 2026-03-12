import json
import math
import warnings
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover - guarded at runtime
    XGBClassifier = None  # type: ignore[assignment]


MISSING_DELAY_SENTINEL = 999.0
MISSING_POINTS_SENTINEL = -1.0

GROUP_KEY_COLUMNS = ["subject_abbr", "semester_id", "student_login"]
MODEL_META_COLUMNS = [
    *GROUP_KEY_COLUMNS,
    "semester_code",
    "teacher_username",
    "available_assignment_count",
    "target_pass",
]

EXPORT_COLUMNS = [
    "subject_abbr",
    "subject_name",
    "semester_id",
    "semester_code",
    "semester_year",
    "semester_winter",
    "semester_begin",
    "semester_end",
    "semester_active",
    "class_id",
    "class_code",
    "teacher_id",
    "teacher_username",
    "student_login",
    "assignment_id",
    "task_id",
    "task_name",
    "task_code",
    "task_type",
    "assigned_at",
    "deadline",
    "assignment_order",
    "assigned_points",
    "max_points",
    "points_ratio",
    "submit_count",
    "graded_submit_count",
    "first_submit_at",
    "first_submit_delay_hours",
    "first_graded_submit_at",
    "first_graded_delay_hours",
    "has_final_submit",
]


@dataclass
class StageDataset:
    stage: int
    frame: pd.DataFrame
    X: pd.DataFrame
    y: pd.Series
    feature_columns: list[str]


@dataclass
class TrainParams:
    objective: str = "binary:logistic"
    eval_metric: str = "auc"
    n_estimators: int = 400
    learning_rate: float = 0.05
    max_depth: int = 4
    subsample: float = 0.9
    colsample_bytree: float = 0.9
    reg_lambda: float = 1.0
    random_state: int = 42
    early_stopping_rounds: int = 30
    decision_threshold: float = 0.5


@dataclass
class TrainResult:
    models: dict[int, Any] = field(default_factory=dict)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    feature_columns: dict[int, list[str]] = field(default_factory=dict)
    split_info: dict[int, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def build_export_dataframe(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=EXPORT_COLUMNS)

    frame = pd.DataFrame.from_records(records)
    for column in EXPORT_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA

    return frame[EXPORT_COLUMNS]


def build_stage_datasets(
    df: pd.DataFrame,
    pass_threshold: float,
    exclude_task_types: set[str],
    max_stage: int | None = None,
) -> dict[int, StageDataset]:
    frame = _normalize_dataframe(df)
    excluded = {task_type.lower() for task_type in exclude_task_types}
    non_project_frame = frame.loc[~frame["task_type_norm"].isin(excluded)].copy()
    if non_project_frame.empty:
        raise ValueError("No assignments available after excluding task types")

    labels = _build_pass_labels(non_project_frame, pass_threshold)

    grouped = []
    for group_key, group in non_project_frame.groupby(GROUP_KEY_COLUMNS, sort=False):
        ordered = group.sort_values(
            by=["assignment_order", "assigned_at", "assignment_id"], kind="mergesort"
        ).reset_index(drop=True)
        if ordered.empty:
            continue
        grouped.append((group_key, ordered))

    if not grouped:
        raise ValueError("No student-semester groups available for stage dataset creation")

    max_available_stage = max(len(group) for _, group in grouped)
    final_stage = max_stage if max_stage is not None else max_available_stage
    if final_stage <= 0:
        raise ValueError("Stage count must be at least 1")

    stage_datasets: dict[int, StageDataset] = {}

    for stage in range(1, final_stage + 1):
        stage_rows: list[dict[str, Any]] = []
        for group_key, group in grouped:
            base_row = _build_stage_feature_row(group, stage)
            target = int(labels.get(group_key, 0))
            base_row.update(
                {
                    "subject_abbr": group_key[0],
                    "semester_id": int(group_key[1]),
                    "student_login": str(group_key[2]),
                    "semester_code": str(group.iloc[0]["semester_code"]),
                    "teacher_username": str(group.iloc[0]["teacher_username"]),
                    "available_assignment_count": int(len(group)),
                    "target_pass": target,
                }
            )
            stage_rows.append(base_row)

        stage_frame = pd.DataFrame(stage_rows)
        teacher_dummies = pd.get_dummies(
            stage_frame["teacher_username"], prefix="teacher", dtype=float
        )
        base_feature_columns = sorted(
            [
                column
                for column in stage_frame.columns
                if column.startswith("a") or column.startswith("cum_")
            ]
        )
        X = pd.concat([stage_frame[base_feature_columns].astype(float), teacher_dummies], axis=1)
        feature_columns = list(X.columns)
        y = stage_frame["target_pass"].astype(int)

        stage_datasets[stage] = StageDataset(
            stage=stage, frame=stage_frame, X=X, y=y, feature_columns=feature_columns
        )

    return stage_datasets


def train_stage_models(
    stage_datasets: dict[int, StageDataset],
    holdout_semester_id: int,
    params: TrainParams,
) -> TrainResult:
    _ensure_xgboost_available()
    result = TrainResult()

    for stage in sorted(stage_datasets):
        dataset = stage_datasets[stage]
        split = _build_split_masks(dataset.frame, holdout_semester_id)

        X_train = dataset.X.loc[split["train_mask"]]
        y_train = dataset.y.loc[split["train_mask"]]
        X_val = dataset.X.loc[split["val_mask"]]
        y_val = dataset.y.loc[split["val_mask"]]

        if y_train.nunique() < 2:
            warning = (
                f"Stage {stage} skipped: training split has only one class "
                f"(strategy={split['strategy']})."
            )
            warnings.warn(warning)
            result.warnings.append(warning)
            continue

        model_kwargs: dict[str, Any] = dict(
            objective=params.objective,
            eval_metric=params.eval_metric,
            n_estimators=params.n_estimators,
            learning_rate=params.learning_rate,
            max_depth=params.max_depth,
            subsample=params.subsample,
            colsample_bytree=params.colsample_bytree,
            reg_lambda=params.reg_lambda,
            random_state=params.random_state,
        )
        if not X_val.empty:
            model_kwargs["early_stopping_rounds"] = params.early_stopping_rounds

        model = XGBClassifier(**model_kwargs)

        fit_kwargs: dict[str, Any] = {}
        if not X_val.empty:
            fit_kwargs["eval_set"] = [(X_val, y_val)]
            fit_kwargs["verbose"] = False

        model.fit(X_train, y_train, **fit_kwargs)

        if X_val.empty:
            eval_X = X_train
            eval_y = y_train
        else:
            eval_X = X_val
            eval_y = y_val

        probability = model.predict_proba(eval_X)[:, 1]
        metrics = _calculate_binary_metrics(
            eval_y.to_numpy(dtype=int),
            probability,
            decision_threshold=params.decision_threshold,
        )
        metrics.update(
            {
                "stage": stage,
                "split_strategy": split["strategy"],
                "train_rows": int(split["train_mask"].sum()),
                "val_rows": int(split["val_mask"].sum()),
                "train_semesters": split["train_semesters"],
                "val_semesters": split["val_semesters"],
            }
        )

        result.models[stage] = model
        result.feature_columns[stage] = dataset.feature_columns
        result.metrics.append(metrics)
        result.split_info[stage] = {
            "strategy": split["strategy"],
            "train_rows": int(split["train_mask"].sum()),
            "val_rows": int(split["val_mask"].sum()),
            "train_semesters": split["train_semesters"],
            "val_semesters": split["val_semesters"],
        }

    return result


def save_train_artifacts(
    train_result: TrainResult,
    output_dir: Path,
    subject_abbr: str,
    pass_threshold: float,
    exclude_task_types: set[str],
    holdout_semester_id: int,
    params: TrainParams,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = output_dir / "metrics.csv"
    metrics_frame = pd.DataFrame(train_result.metrics)
    metrics_frame.to_csv(metrics_path, index=False)

    for stage, model in train_result.models.items():
        model_path = output_dir / f"stage_{stage}.json"
        model.get_booster().save_model(str(model_path))

        features_path = output_dir / f"stage_{stage}_features.json"
        features_path.write_text(
            json.dumps(train_result.feature_columns[stage], ensure_ascii=True, indent=2)
        )

    manifest = {
        "subject_abbr": subject_abbr,
        "pass_threshold": pass_threshold,
        "exclude_task_types": sorted(exclude_task_types),
        "holdout_semester_id": holdout_semester_id,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "stages": sorted(train_result.models.keys()),
        "feature_schema": train_result.feature_columns,
        "metrics": train_result.metrics,
        "split_info": train_result.split_info,
        "warnings": train_result.warnings,
        "train_params": asdict(params),
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2))
    return manifest


def predict_from_models(
    df: pd.DataFrame,
    artifacts_dir: Path,
    decision_threshold: float,
    all_stages: bool,
) -> pd.DataFrame:
    _ensure_xgboost_available()
    manifest_path = artifacts_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    model_stages = sorted(int(stage) for stage in manifest.get("stages", []))
    if not model_stages:
        raise ValueError("No stages found in manifest")

    pass_threshold = float(manifest.get("pass_threshold", 18.0))
    exclude_task_types = set(manifest.get("exclude_task_types", ["project"]))
    max_stage = max(model_stages)

    stage_datasets = build_stage_datasets(
        df=df,
        pass_threshold=pass_threshold,
        exclude_task_types=exclude_task_types,
        max_stage=max_stage,
    )

    prediction_frames: list[pd.DataFrame] = []
    for stage in model_stages:
        if stage not in stage_datasets:
            continue
        dataset = stage_datasets[stage]
        model = XGBClassifier()
        model.load_model(str(artifacts_dir / f"stage_{stage}.json"))

        expected_features_path = artifacts_dir / f"stage_{stage}_features.json"
        expected_features = json.loads(expected_features_path.read_text())
        X = _align_feature_columns(dataset.X.copy(), expected_features)
        probability = model.predict_proba(X)[:, 1]

        prediction_frame = dataset.frame[
            ["subject_abbr", "semester_id", "semester_code", "teacher_username", "student_login"]
        ].copy()
        prediction_frame["stage"] = stage
        prediction_frame["model_stage_used"] = stage
        prediction_frame["available_assignment_count"] = dataset.frame["available_assignment_count"]
        prediction_frame["pass_probability"] = probability
        prediction_frames.append(prediction_frame)

    if not prediction_frames:
        return pd.DataFrame(
            columns=[
                "student_login",
                "semester_id",
                "semester_code",
                "teacher_username",
                "stage",
                "pass_probability",
                "predicted_pass",
                "decision_threshold",
                "model_stage_used",
                "generated_at",
            ]
        )

    predictions = pd.concat(prediction_frames, ignore_index=True)
    generated_at = datetime.now(tz=timezone.utc).isoformat()

    if all_stages:
        result = predictions.copy()
    else:
        chosen_stage = (
            predictions.groupby(GROUP_KEY_COLUMNS, as_index=False)["available_assignment_count"]
            .max()
            .rename(columns={"available_assignment_count": "chosen_stage"})
        )
        chosen_stage["chosen_stage"] = chosen_stage["chosen_stage"].clip(lower=1, upper=max_stage)
        result = predictions.merge(
            chosen_stage,
            how="inner",
            on=GROUP_KEY_COLUMNS,
        )
        result = result.loc[result["stage"] == result["chosen_stage"]].copy()
        result.drop(columns=["chosen_stage"], inplace=True)

    result["predicted_pass"] = (result["pass_probability"] >= decision_threshold).astype(int)
    result["decision_threshold"] = decision_threshold
    result["generated_at"] = generated_at

    result = result[
        [
            "student_login",
            "semester_id",
            "semester_code",
            "teacher_username",
            "stage",
            "pass_probability",
            "predicted_pass",
            "decision_threshold",
            "model_stage_used",
            "generated_at",
        ]
    ].sort_values(by=["semester_id", "student_login", "stage"], kind="mergesort")

    return result.reset_index(drop=True)


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {
        "subject_abbr",
        "semester_id",
        "semester_code",
        "teacher_username",
        "student_login",
        "assignment_id",
        "assignment_order",
        "task_type",
        "assigned_points",
        "points_ratio",
        "submit_count",
        "graded_submit_count",
        "first_submit_delay_hours",
        "first_graded_delay_hours",
        "assigned_at",
    }
    missing = required_columns - set(df.columns)
    if missing:
        missing_columns = ", ".join(sorted(missing))
        raise ValueError(f"Missing columns in dataframe: {missing_columns}")

    frame = df.copy()
    frame["subject_abbr"] = frame["subject_abbr"].astype(str).str.upper()
    frame["semester_id"] = pd.to_numeric(frame["semester_id"], errors="coerce").astype("Int64")
    frame["semester_id"] = frame["semester_id"].fillna(-1).astype(int)
    frame["semester_code"] = frame["semester_code"].astype(str)
    frame["teacher_username"] = frame["teacher_username"].fillna("unknown").astype(str)
    frame["student_login"] = frame["student_login"].astype(str)
    frame["assignment_id"] = pd.to_numeric(frame["assignment_id"], errors="coerce").astype("Int64")
    frame["assignment_id"] = frame["assignment_id"].fillna(-1).astype(int)
    frame["assignment_order"] = pd.to_numeric(frame["assignment_order"], errors="coerce").astype(
        "Int64"
    )
    frame["assignment_order"] = frame["assignment_order"].fillna(0).astype(int)
    frame["assigned_at"] = pd.to_datetime(frame["assigned_at"], errors="coerce")

    for column in [
        "assigned_points",
        "points_ratio",
        "submit_count",
        "graded_submit_count",
        "first_submit_delay_hours",
        "first_graded_delay_hours",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["task_type_norm"] = frame["task_type"].fillna("").astype(str).str.lower()
    return frame


def _build_pass_labels(
    frame: pd.DataFrame, pass_threshold: float
) -> dict[tuple[str, int, str], int]:
    points_per_group = (
        frame.assign(assigned_points=frame["assigned_points"].fillna(0.0))
        .groupby(GROUP_KEY_COLUMNS, as_index=False)["assigned_points"]
        .sum()
    )
    labels: dict[tuple[str, int, str], int] = {}
    for row in points_per_group.itertuples(index=False):
        key = (str(row.subject_abbr), int(row.semester_id), str(row.student_login))
        labels[key] = int(float(row.assigned_points) >= pass_threshold)
    return labels


def _build_stage_feature_row(group: pd.DataFrame, stage: int) -> dict[str, float]:
    row: dict[str, float] = {}
    point_pairs: list[tuple[int, float]] = []
    known_points: list[float] = []
    known_ratios: list[float] = []
    known_submit_delays: list[float] = []
    known_graded_delays: list[float] = []

    cumulative_submit_count = 0.0
    cumulative_graded_submit_count = 0.0
    cumulative_missing_grade_count = 0.0

    for index in range(1, stage + 1):
        prefix = f"a{index}"
        assignment = group.iloc[index - 1] if index <= len(group) else None

        if assignment is None:
            points_value = MISSING_POINTS_SENTINEL
            ratio_value = MISSING_POINTS_SENTINEL
            submit_count = 0.0
            graded_submit_count = 0.0
            first_submit_delay = MISSING_DELAY_SENTINEL
            first_graded_delay = MISSING_DELAY_SENTINEL
            has_submit = 0.0
            has_graded_submit = 0.0
        else:
            points = assignment["assigned_points"]
            ratio = assignment["points_ratio"]
            submit = assignment["submit_count"]
            graded_submit = assignment["graded_submit_count"]
            submit_delay = assignment["first_submit_delay_hours"]
            graded_delay = assignment["first_graded_delay_hours"]

            points_value = (
                float(points) if pd.notna(points) else float(MISSING_POINTS_SENTINEL)
            )
            ratio_value = float(ratio) if pd.notna(ratio) else float(MISSING_POINTS_SENTINEL)
            submit_count = float(submit) if pd.notna(submit) else 0.0
            graded_submit_count = float(graded_submit) if pd.notna(graded_submit) else 0.0
            first_submit_delay = (
                float(submit_delay) if pd.notna(submit_delay) else float(MISSING_DELAY_SENTINEL)
            )
            first_graded_delay = (
                float(graded_delay) if pd.notna(graded_delay) else float(MISSING_DELAY_SENTINEL)
            )
            has_submit = 1.0 if submit_count > 0 else 0.0
            has_graded_submit = 1.0 if graded_submit_count > 0 else 0.0

        row[f"{prefix}_points_assigned"] = points_value
        row[f"{prefix}_points_ratio"] = ratio_value
        row[f"{prefix}_submit_count"] = submit_count
        row[f"{prefix}_graded_submit_count"] = graded_submit_count
        row[f"{prefix}_first_submit_delay_hours"] = first_submit_delay
        row[f"{prefix}_first_graded_delay_hours"] = first_graded_delay
        row[f"{prefix}_has_submit"] = has_submit
        row[f"{prefix}_has_graded_submit"] = has_graded_submit

        cumulative_submit_count += submit_count
        cumulative_graded_submit_count += graded_submit_count
        if has_graded_submit == 0:
            cumulative_missing_grade_count += 1

        if points_value != MISSING_POINTS_SENTINEL:
            known_points.append(points_value)
            point_pairs.append((index, points_value))
        if ratio_value != MISSING_POINTS_SENTINEL:
            known_ratios.append(ratio_value)
        if first_submit_delay != MISSING_DELAY_SENTINEL:
            known_submit_delays.append(first_submit_delay)
        if first_graded_delay != MISSING_DELAY_SENTINEL:
            known_graded_delays.append(first_graded_delay)

    row["cum_points_sum"] = float(sum(known_points))
    row["cum_points_mean"] = (
        float(sum(known_points) / len(known_points)) if known_points else MISSING_POINTS_SENTINEL
    )
    row["cum_points_ratio_sum"] = float(sum(known_ratios))
    row["cum_points_ratio_mean"] = (
        float(sum(known_ratios) / len(known_ratios))
        if known_ratios
        else MISSING_POINTS_SENTINEL
    )
    row["cum_submit_count"] = cumulative_submit_count
    row["cum_graded_submit_count"] = cumulative_graded_submit_count
    row["cum_missing_grade_count"] = cumulative_missing_grade_count
    row["cum_avg_first_submit_delay_hours"] = (
        float(sum(known_submit_delays) / len(known_submit_delays))
        if known_submit_delays
        else MISSING_DELAY_SENTINEL
    )
    row["cum_avg_first_graded_delay_hours"] = (
        float(sum(known_graded_delays) / len(known_graded_delays))
        if known_graded_delays
        else MISSING_DELAY_SENTINEL
    )
    row["cum_point_trend_slope"] = _calculate_slope(point_pairs)

    return row


def _calculate_slope(pairs: list[tuple[int, float]]) -> float:
    if len(pairs) < 2:
        return 0.0

    x = np.array([pair[0] for pair in pairs], dtype=float)
    y = np.array([pair[1] for pair in pairs], dtype=float)
    x_mean = float(x.mean())
    y_mean = float(y.mean())
    numerator = float(np.sum((x - x_mean) * (y - y_mean)))
    denominator = float(np.sum((x - x_mean) ** 2))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _build_split_masks(frame: pd.DataFrame, holdout_semester_id: int) -> dict[str, Any]:
    semester_ids = sorted(int(value) for value in frame["semester_id"].unique())
    temporal_val_mask = frame["semester_id"] == holdout_semester_id
    temporal_train_mask = ~temporal_val_mask

    if temporal_val_mask.any() and temporal_train_mask.any():
        return {
            "strategy": "temporal_holdout",
            "train_mask": temporal_train_mask,
            "val_mask": temporal_val_mask,
            "train_semesters": sorted(set(frame.loc[temporal_train_mask, "semester_id"].tolist())),
            "val_semesters": sorted(set(frame.loc[temporal_val_mask, "semester_id"].tolist())),
        }

    student_ids = sorted(frame["student_login"].astype(str).unique())
    if len(student_ids) < 2:
        return {
            "strategy": "single_group",
            "train_mask": pd.Series([True] * len(frame), index=frame.index),
            "val_mask": pd.Series([False] * len(frame), index=frame.index),
            "train_semesters": semester_ids,
            "val_semesters": [],
        }

    split_index = max(1, math.floor(len(student_ids) * 0.8))
    train_students = set(student_ids[:split_index])
    val_students = set(student_ids[split_index:])
    train_mask = frame["student_login"].isin(train_students)
    val_mask = frame["student_login"].isin(val_students)

    return {
        "strategy": "deterministic_80_20_student_split",
        "train_mask": train_mask,
        "val_mask": val_mask,
        "train_semesters": semester_ids,
        "val_semesters": semester_ids,
    }


def _calculate_binary_metrics(
    y_true: np.ndarray, y_probability: np.ndarray, decision_threshold: float
) -> dict[str, float | None]:
    y_pred = (y_probability >= decision_threshold).astype(int)

    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))

    total = len(y_true)
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    roc_auc = _binary_roc_auc(y_true, y_probability)

    return {
        "roc_auc": roc_auc,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _binary_roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    positives = np.sum(y_true == 1)
    negatives = np.sum(y_true == 0)
    if positives == 0 or negatives == 0:
        return None

    order = np.argsort(y_score)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1, dtype=float)

    sorted_scores = y_score[order]
    start = 0
    while start < len(sorted_scores):
        end = start + 1
        while end < len(sorted_scores) and sorted_scores[end] == sorted_scores[start]:
            end += 1
        if end - start > 1:
            tie_indexes = order[start:end]
            mean_rank = float(np.mean(ranks[tie_indexes]))
            ranks[tie_indexes] = mean_rank
        start = end

    sum_rank_pos = float(np.sum(ranks[y_true == 1]))
    auc = (sum_rank_pos - positives * (positives + 1) / 2) / (positives * negatives)
    return auc


def _align_feature_columns(frame: pd.DataFrame, expected_columns: list[str]) -> pd.DataFrame:
    aligned = frame.copy()
    for column in expected_columns:
        if column not in aligned:
            aligned[column] = 0.0
    return aligned[expected_columns]


def _ensure_xgboost_available() -> None:
    if XGBClassifier is None:
        raise ImportError(
            "xgboost is not available. Install project dependencies before training or prediction."
        )
