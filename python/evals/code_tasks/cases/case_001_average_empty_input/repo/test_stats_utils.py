import unittest

from stats_utils import average


class AverageTests(unittest.TestCase):
    def test_average_numbers(self):
        self.assertEqual(average([2, 4, 6]), 4)

    def test_empty_input_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            average([])


if __name__ == "__main__":
    unittest.main()

