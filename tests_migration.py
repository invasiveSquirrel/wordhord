import unittest
from migrate_to_sqlite import validate_card_data

class TestMigration(unittest.TestCase):
    def test_validate_valid_card(self):
        self.assertTrue(validate_card_data("german", "der Hund", "the dog"))

    def test_validate_empty_term(self):
        self.assertFalse(validate_card_data("german", "", "the dog"))

    def test_validate_empty_translation(self):
        self.assertFalse(validate_card_data("german", "der Hund", ""))

    def test_validate_long_term(self):
        self.assertFalse(validate_card_data("german", "a" * 101, "the dog"))

    def test_validate_long_translation(self):
        self.assertFalse(validate_card_data("german", "der Hund", "b" * 201))

    def test_validate_markdown_syntax(self):
        self.assertFalse(validate_card_data("german", "**der Hund**", "the dog"))
        self.assertFalse(validate_card_data("german", "der Hund", "the **dog**"))

    def test_validate_newlines(self):
        self.assertFalse(validate_card_data("german", "der\nHund", "the dog"))

if __name__ == '__main__':
    unittest.main()
