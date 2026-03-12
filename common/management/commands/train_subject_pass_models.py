from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from common.ml import (
    TrainParams,
    build_stage_datasets,
    save_train_artifacts,
    train_stage_models,
)


class Command(BaseCommand):
    help = "Train staged XGBoost pass/fail models for a selected subject."

    def add_arguments(self, parser):
        parser.add_argument("subject_abbr", type=str)
        parser.add_argument("--input-csv", required=True, type=str)
        parser.add_argument("--output-dir", required=True, type=str)
        parser.add_argument("--pass-threshold", type=float, default=18.0)
        parser.add_argument(
            "--exclude-task-types",
            type=str,
            default="project",
            help="Comma-separated task types to exclude from training and label calculation.",
        )
        parser.add_argument(
            "--max-stage",
            type=int,
            default=None,
            help="Maximum stage index to train. By default inferred from data.",
        )
        parser.add_argument(
            "--decision-threshold",
            type=float,
            default=0.5,
            help="Threshold used for reporting threshold-based metrics.",
        )

    def handle(self, *args, **options):
        subject_abbr = str(options["subject_abbr"]).upper()
        input_csv = Path(options["input_csv"])
        output_dir = Path(options["output_dir"])
        pass_threshold = float(options["pass_threshold"])
        exclude_task_types = self._parse_task_types(options["exclude_task_types"])
        max_stage = options["max_stage"]

        if not input_csv.exists():
            raise CommandError(f"Input CSV does not exist: {input_csv}")

        frame = pd.read_csv(input_csv)
        if frame.empty:
            raise CommandError("Input CSV is empty")
        if "subject_abbr" not in frame.columns:
            raise CommandError("Input CSV does not contain required column 'subject_abbr'")

        frame = frame.loc[frame["subject_abbr"].astype(str).str.upper() == subject_abbr].copy()
        if frame.empty:
            raise CommandError(f"No rows found for subject {subject_abbr} in {input_csv}")

        holdout_semester_id = self._resolve_holdout_semester_id(frame)
        train_params = TrainParams(decision_threshold=float(options["decision_threshold"]))

        stage_datasets = build_stage_datasets(
            frame,
            pass_threshold=pass_threshold,
            exclude_task_types=exclude_task_types,
            max_stage=max_stage,
        )
        train_result = train_stage_models(
            stage_datasets=stage_datasets,
            holdout_semester_id=holdout_semester_id,
            params=train_params,
        )
        if not train_result.models:
            raise CommandError("No models were trained. Check class balance in historical data.")

        manifest = save_train_artifacts(
            train_result=train_result,
            output_dir=output_dir,
            subject_abbr=subject_abbr,
            pass_threshold=pass_threshold,
            exclude_task_types=exclude_task_types,
            holdout_semester_id=holdout_semester_id,
            params=train_params,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Trained staged models: "
                f"{manifest['stages']} (holdout semester={holdout_semester_id})"
            )
        )
        if train_result.warnings:
            for warning in train_result.warnings:
                self.stdout.write(self.style.WARNING(warning))

    def _parse_task_types(self, value: str) -> set[str]:
        return {token.strip().lower() for token in value.split(",") if token.strip()}

    def _resolve_holdout_semester_id(self, frame: pd.DataFrame) -> int:
        local_today = timezone.localdate()
        if "semester_end" in frame.columns:
            frame = frame.copy()
            frame["semester_end"] = pd.to_datetime(frame["semester_end"], errors="coerce")
            completed = frame.loc[frame["semester_end"].dt.date < local_today]
            if not completed.empty:
                ordered = completed.sort_values(by=["semester_end", "semester_id"])
                return int(ordered.iloc[-1]["semester_id"])

        if "semester_active" in frame.columns:
            inactive = frame.loc[~frame["semester_active"].fillna(False)]
            if not inactive.empty:
                return int(inactive.sort_values(by=["semester_id"]).iloc[-1]["semester_id"])

        return int(frame.sort_values(by=["semester_id"]).iloc[-1]["semester_id"])
