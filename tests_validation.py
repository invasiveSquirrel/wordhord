import unittest
import sys
import os

# Add backend directory to sys.path so we can import main
sys.path.insert(0, '/home/chris/wordhord/backend')
from main import CardCreate

class TestValidationAndLanguage(unittest.TestCase):
    def test_phrasal_verb_german(self):
        # Should not raise exception
        card = CardCreate(
            language="German",
            term="auf den Tisch legen",
            translation="to put on the table",
            example="Ich lege das Buch auf den Tisch.",
            example_translation="I put the book on the table.",
            part_of_speech="verb phrase",
            ipa="[aʊf deːn tɪʃ ˈleːgən]"
        )
        # Assuming the validator returns the object if successful
        self.assertEqual(card.term, "auf den Tisch legen")

    def test_german_detected_as_german_no_example(self):
        # A German word detected as German without an example should NOT fail
        # 'Hund' is detected as German or at least not English
        card = CardCreate(
            language="German",
            term="Gesundheit",
            translation="health",
            example="",
            example_translation="",
            part_of_speech="noun"
        )
        self.assertEqual(card.term, "Gesundheit")

    def test_english_in_german_no_example(self):
        # An English word detected as English in German target language with NO example should fail
        # We use a longer English phrase so it's reliably detected as English
        with self.assertRaises(ValueError) as context:
            CardCreate(
                language="German",
                term="the quick brown fox jumps over the lazy dog",
                translation="something else entirely different",
                example="",
                example_translation="",
                part_of_speech="noun"
            )
        self.assertIn("Suspected incorrect language insertion", str(context.exception))

    def test_german_inverted_with_english(self):
        # If term is English and translation is German, it should swap them
        card = CardCreate(
            language="German",
            term="to write",
            translation="schreiben",
            example="Ich schreibe.",
            example_translation="I write.",
            part_of_speech="verb"
        )
        # Should be swapped
        self.assertEqual(card.term, "schreiben")
        self.assertEqual(card.translation, "to write")

    def test_swedish_german_exclusion(self):
        # Suffixes like "ung" in Swedish should raise error
        with self.assertRaises(ValueError) as context:
            CardCreate(
                language="Swedish",
                term="die Bedeutung",
                translation="the meaning",
                example="Das ist eine Bedeutung.",
                example_translation="That is a meaning.",
                part_of_speech="noun",
                tone="1", ipa="[x]"
            )
        self.assertIn("appears to be of German origin", str(context.exception))

if __name__ == '__main__':
    unittest.main()
