from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from common.ml import build_export_dataframe
from common.models import Semester, Subject, extract_subject_assignment_points


class Command(BaseCommand):
    help = "Export student assignment points/timing records for a selected subject to CSV."

    def add_arguments(self, parser):
        parser.add_argument("subject_abbr", type=str)
        parser.add_argument("--output", required=True, type=str)
        parser.add_argument(
            "--semester-ids",
            type=str,
            default=None,
            help="Comma-separated semester IDs to include (e.g. 1,2,3).",
        )
        parser.add_argument(
            "--include-active",
            action="store_true",
            help=(
                "Include active and future semesters. "
                "By default only completed semesters are used."
            ),
        )
        parser.add_argument(
            "--pass-threshold",
            type=float,
            default=18.0,
            help="Stored in export metadata columns only.",
        )

    def handle(self, *args, **options):
        subject_abbr = str(options["subject_abbr"]).upper()
        output = Path(options["output"])
        include_active = bool(options["include_active"])
        semester_ids = self._parse_semester_ids(options["semester_ids"])

        if not Subject.objects.filter(abbr__iexact=subject_abbr).exists():
            raise CommandError(f"Unknown subject abbreviation: {subject_abbr}")

        if semester_ids is None and not include_active:
            semester_ids = list(
                Semester.objects.filter(end__lt=timezone.localdate()).values_list("id", flat=True)
            )

        records = extract_subject_assignment_points(subject_abbr, semester_ids=semester_ids)
        frame = build_export_dataframe(records)
        frame["exported_at"] = timezone.now().isoformat()
        frame["export_pass_threshold"] = float(options["pass_threshold"])

        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output, index=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {len(frame)} rows for subject {subject_abbr} to {output}"
            )
        )

    def _parse_semester_ids(self, raw_value: str | None) -> list[int] | None:
        if raw_value is None:
            return None

        parts = [token.strip() for token in raw_value.split(",") if token.strip()]
        if not parts:
            return []

        try:
            return [int(token) for token in parts]
        except ValueError as exc:
            raise CommandError("--semester-ids must contain comma-separated integers") from exc
