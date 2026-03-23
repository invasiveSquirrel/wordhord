import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from synonyms import get_synonyms, _get_datamuse, _get_merriam_webster, _get_oxford, ThesaurusAPIError

class TestSynonyms(unittest.TestCase):
    
    @patch('synonyms.requests.get')
    def test_get_datamuse(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"word": "quick", "score": 100},
            {"word": "swift", "score": 90},
            {"word": "rapid", "score": 80},
            {"word": "speedy", "score": 70},
            {"word": "fleet", "score": 60},
            {"word": "brisk", "score": 50},
        ]
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = _get_datamuse("fast", "en")
        
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], "quick")
        self.assertEqual(result[4], "fleet")
        mock_get.assert_called_once()
        self.assertIn("rel_syn=fast", mock_get.call_args[0][0])

    @patch('synonyms.os.environ.get')
    @patch('synonyms.requests.get')
    def test_get_merriam_webster(self, mock_get, mock_env):
        mock_env.return_value = "fake_api_key"
        
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "meta": {
                    "syns": [
                        ["quick", "swift", "rapid"],
                        ["speedy", "fleet", "brisk"]
                    ]
                }
            }
        ]
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = _get_merriam_webster("fast", "en")
        
        self.assertEqual(len(result), 5)
        self.assertEqual(result, ["quick", "swift", "rapid", "speedy", "fleet"])
        mock_get.assert_called_once()

    @patch('synonyms.os.environ.get')
    def test_get_merriam_webster_missing_key(self, mock_env):
        mock_env.return_value = None
        with self.assertRaises(ThesaurusAPIError):
            _get_merriam_webster("fast", "en")

    @patch('synonyms.requests.get')
    def test_get_synonyms_retry(self, mock_get):
        # Simulate transient error then success
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Network error"),
            MagicMock(status_code=200, json=lambda: [{"word": "quick"}])
        ]
        
        result = get_synonyms("fast", "en", "dm")
        self.assertEqual(result, ["quick"])
        self.assertEqual(mock_get.call_count, 2)

if __name__ == '__main__':
    # Needs requests module available
    import requests
    unittest.main()
