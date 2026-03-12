# Student Pass Prediction Pipeline

This directory contains the reusable ML logic for staged student pass/fail prediction.

## What This Pipeline Does

1. Exports per-student, per-assignment records for a selected subject.
2. Trains staged XGBoost models:
   - stage 1 uses assignment 1
   - stage 2 uses assignments 1-2
   - ...
3. Predicts pass probability and pass/fail flag for new semester data.

Defaults:
- pass threshold: `18`
- excluded task type from training and label: `project`
- decision threshold for pass/fail classification: `0.5`

## Prerequisites

From repository root:

```bash
uv sync
```

This installs required dependencies into `.venv`, including `xgboost` and `scikit-learn`.

## End-to-End Usage

Run all commands from repository root.

### 1) Export historical training data

```bash
.venv/bin/python manage.py export_subject_points_csv UPR \
  --output /tmp/upr_history.csv
```

Useful options:
- `--semester-ids 1,2,3` limit export to selected semesters
- `--include-active` include active/future semesters (default export uses completed only)
- `--pass-threshold 18` writes threshold metadata into export file

### 2) Train staged models

```bash
.venv/bin/python manage.py train_subject_pass_models UPR \
  --input-csv /tmp/upr_history.csv \
  --output-dir /tmp/upr_models \
  --pass-threshold 18 \
  --exclude-task-types project \
  --decision-threshold 0.5
```

Useful options:
- `--max-stage 10` cap maximum trained stage

### 3) Export next-semester data for prediction

Example: export only active semester(s):

```bash
.venv/bin/python manage.py export_subject_points_csv UPR \
  --output /tmp/upr_next_semester.csv \
  --include-active
```

### 4) Predict pass risk

```bash
.venv/bin/python manage.py predict_subject_pass_risk UPR \
  --input-csv /tmp/upr_next_semester.csv \
  --artifacts-dir /tmp/upr_models \
  --output /tmp/upr_predictions.csv \
  --decision-threshold 0.5
```

Useful options:
- `--all-stages` output predictions for every stage instead of only current stage

## Produced Files

### Training output directory

- `manifest.json` model metadata and training configuration
- `metrics.csv` stage metrics
- `stage_<N>.json` XGBoost model per stage
- `stage_<N>_features.json` exact feature order per stage

### Prediction output CSV columns

- `student_login`
- `semester_id`
- `semester_code`
- `teacher_username`
- `stage`
- `pass_probability`
- `predicted_pass`
- `decision_threshold`
- `model_stage_used`
- `generated_at`

## Notes

- Export includes all task types (including `project`).
- Training and label creation exclude task types passed via `--exclude-task-types` (default `project`).
- Holdout validation uses latest completed semester; if unavailable, deterministic student split fallback is used.

## Quick Validation

```bash
.venv/bin/python manage.py test \
  common.tests.test_student_pass_prediction \
  common.tests.test_student_pass_commands -v 2
```
