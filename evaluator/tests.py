import unittest
from .utils import parse_human_size


class TestUtils(unittest.TestCase):
    def test_human_size(self):
        self.assertEqual(parse_human_size(1024), 1024)
        self.assertEqual(parse_human_size("1024"), 1024)
        self.assertEqual(parse_human_size("1024 "), 1024)
        self.assertEqual(parse_human_size("1024 B"), 1024)
        self.assertEqual(parse_human_size("1024B"), 1024)
        self.assertEqual(parse_human_size("5 KB"), 5 * 1024)
        self.assertEqual(parse_human_size("5KB"), 5 * 1024)
        self.assertEqual(parse_human_size("5K"), 5 * 1024)
        self.assertEqual(parse_human_size("1.5M"), 1.5 * 1024 * 1024)

        with self.assertRaises(ValueError):
            self.assertEqual(parse_human_size("1.5Z"), 1.5 * 1024 * 1024)

if __name__ == '__main__':
    unittest.main()
