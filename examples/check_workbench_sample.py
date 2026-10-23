"""Behavior checks for the small public editing exercise, not a benchmark."""
import unittest
from examples.workbench_sample import average


class AverageChecks(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(average([]), 0)

    def test_positive_values(self):
        self.assertEqual(average([2, 4]), 3)

    def test_negative_values(self):
        self.assertEqual(average([-4, -2]), -3)


if __name__ == '__main__':
    unittest.main()
