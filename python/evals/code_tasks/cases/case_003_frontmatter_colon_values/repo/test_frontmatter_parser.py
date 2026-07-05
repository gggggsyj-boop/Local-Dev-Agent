import unittest

from frontmatter_parser import parse_frontmatter


class FrontmatterParserTests(unittest.TestCase):
    def test_value_can_contain_colon(self):
        meta, body = parse_frontmatter("---\ntitle: Agent: Tools\nkind: note\n---\nBody")
        self.assertEqual(meta["title"], "Agent: Tools")
        self.assertEqual(meta["kind"], "note")
        self.assertEqual(body, "Body")

    def test_missing_closing_delimiter_is_plain_body(self):
        text = "---\ntitle: unfinished\nBody"
        meta, body = parse_frontmatter(text)
        self.assertEqual(meta, {})
        self.assertEqual(body, text)

    def test_invalid_header_line_is_ignored(self):
        meta, body = parse_frontmatter("---\ntitle: OK\ninvalid line\n---\nBody")
        self.assertEqual(meta, {"title": "OK"})
        self.assertEqual(body, "Body")


if __name__ == "__main__":
    unittest.main()

