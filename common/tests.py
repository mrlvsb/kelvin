from django.test import TestCase
from common.utils import parse_time_interval
from datetime import timedelta


class ParseIntervalTestCase(TestCase):
    def test_minutes(self):
        self.assertEqual(parse_time_interval("30 minute"), timedelta(minutes=30))
        self.assertEqual(parse_time_interval("30 minutes"), timedelta(minutes=30))
        self.assertEqual(parse_time_interval("30 m"), timedelta(minutes=30))
        self.assertEqual(parse_time_interval("30m"), timedelta(minutes=30))
        self.assertEqual(parse_time_interval("30 min"), timedelta(minutes=30))

    def test_hours(self):
        self.assertEqual(parse_time_interval("30 hours"), timedelta(hours=30))
        self.assertEqual(parse_time_interval("30 hour"), timedelta(hours=30))
        self.assertEqual(parse_time_interval("30 h"), timedelta(hours=30))
        self.assertEqual(parse_time_interval("30h"), timedelta(hours=30))

    def test_weeks(self):
        self.assertEqual(parse_time_interval("2 week"), timedelta(weeks=2))
        self.assertEqual(parse_time_interval("2 weeks"), timedelta(weeks=2))

    def test_combined(self):
        self.assertEqual(parse_time_interval("2h30m"), timedelta(hours=2, minutes=30))
        self.assertEqual(parse_time_interval("2 h 30 m"), timedelta(hours=2, minutes=30))
        self.assertEqual(parse_time_interval("2 hours 30 minutes"), timedelta(hours=2, minutes=30))
