import unittest

from slug import slugify


class SlugifyTests(unittest.TestCase):
    def test_punctuation_is_removed(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_repeated_separators_are_collapsed(self):
        self.assertEqual(slugify("  Agent   Loop + Tools  "), "agent-loop-tools")

    def test_empty_text_becomes_empty_slug(self):
        self.assertEqual(slugify(" ... "), "")


if __name__ == "__main__":
    unittest.main()

