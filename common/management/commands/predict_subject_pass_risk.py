from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from common.ml import predict_from_models


class Command(BaseCommand):
    help = "Predict staged pass probability for students from exported CSV input."

    def add_arguments(self, parser):
        parser.add_argument("subject_abbr", type=str)
        parser.add_argument("--input-csv", required=True, type=str)
        parser.add_argument("--artifacts-dir", required=True, type=str)
        parser.add_argument("--output", required=True, type=str)
        parser.add_argument("--decision-threshold", type=float, default=0.5)
        parser.add_argument(
            "--all-stages",
            action="store_true",
            help="Output predictions for all stages. By default, output only the current stage.",
        )

    def handle(self, *args, **options):
        subject_abbr = str(options["subject_abbr"]).upper()
        input_csv = Path(options["input_csv"])
        artifacts_dir = Path(options["artifacts_dir"])
        output = Path(options["output"])
        decision_threshold = float(options["decision_threshold"])
        all_stages = bool(options["all_stages"])

        if not input_csv.exists():
            raise CommandError(f"Input CSV does not exist: {input_csv}")
        if not artifacts_dir.exists():
            raise CommandError(f"Artifacts directory does not exist: {artifacts_dir}")

        frame = pd.read_csv(input_csv)
        if frame.empty:
            raise CommandError("Input CSV is empty")
        if "subject_abbr" not in frame.columns:
            raise CommandError("Input CSV does not contain required column 'subject_abbr'")

        frame = frame.loc[frame["subject_abbr"].astype(str).str.upper() == subject_abbr].copy()
        if frame.empty:
            raise CommandError(f"No rows found for subject {subject_abbr} in {input_csv}")

        prediction = predict_from_models(
            frame,
            artifacts_dir=artifacts_dir,
            decision_threshold=decision_threshold,
            all_stages=all_stages,
        )

        output.parent.mkdir(parents=True, exist_ok=True)
        prediction.to_csv(output, index=False)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(prediction)} predictions to {output}"))
