import os
import requests
import time
from functools import lru_cache
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class ThesaurusAPIError(Exception):
    pass

@lru_cache(maxsize=1000)
def get_synonyms(word: str, lang: str = "en", source: str = "dm") -> List[str]:
    """
    Fetch top 5 synonyms for a word using the specified source.
    Language defaults to 'en' (ISO 639-1).
    sources: 'dm' (Datamuse), 'mw' (Merriam-Webster), 'ox' (Oxford)
    """
    retries = 3
    for attempt in range(retries):
        try:
            if source == "dm":
                return _get_datamuse(word, lang)
            elif source == "mw":
                return _get_merriam_webster(word, lang)
            elif source == "ox":
                return _get_oxford(word, lang)
            else:
                raise ValueError(f"Unknown source: {source}")
        except (requests.RequestException, ThesaurusAPIError) as e:
            if attempt < retries - 1:
                time.sleep(1 * (attempt + 1))
            else:
                print(f"Error fetching synonyms from {source} for word {word}: {e}")
                return []
    return []

def _get_datamuse(word: str, lang: str) -> List[str]:
    # Datamuse mainly supports English (en) and Spanish (es).
    v = 'es' if lang.lower() == 'es' else 'en'
    url = f"https://api.datamuse.com/words?rel_syn={word}&v={v}"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    data = response.json()
    return [item['word'] for item in data[:5]]

def _get_merriam_webster(word: str, lang: str) -> List[str]:
    api_key = os.environ.get("MW_THESAURUS_API_KEY")
    if not api_key:
        raise ThesaurusAPIError("MW_THESAURUS_API_KEY environment variable not set.")
    
    url = f"https://www.dictionaryapi.com/api/v3/references/thesaurus/json/{word}?key={api_key}"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    data = response.json()
    
    synonyms = []
    if data and isinstance(data, list):
        if isinstance(data[0], dict) and "meta" in data[0] and "syns" in data[0]["meta"]:
            for syn_list in data[0]["meta"]["syns"]:
                synonyms.extend(syn_list)
                if len(synonyms) >= 5:
                    break
    
    # Deduplicate and limit
    seen = set()
    result = []
    for s in synonyms:
        if s not in seen:
            seen.add(s)
            result.append(s)
        if len(result) == 5:
            break
    return result

def _get_oxford(word: str, lang: str) -> List[str]:
    app_id = os.environ.get("OXFORD_APP_ID")
    app_key = os.environ.get("OXFORD_APP_KEY")
    if not app_id or not app_key:
        raise ThesaurusAPIError("OXFORD_APP_ID or OXFORD_APP_KEY environment variables not set.")
    
    url = f"https://od-api.oxforddictionaries.com/api/v2/thesaurus/{lang}/{word}"
    headers = {"app_id": app_id, "app_key": app_key}
    response = requests.get(url, headers=headers, timeout=5)
    
    if response.status_code == 404:
        return []
    response.raise_for_status()
    
    data = response.json()
    synonyms = []
    try:
        results = data.get("results", [])
        for res in results:
            for lexicalEntry in res.get("lexicalEntries", []):
                for entry in lexicalEntry.get("entries", []):
                    for sense in entry.get("senses", []):
                        for syn in sense.get("synonyms", []):
                            synonyms.append(syn.get("text"))
                            if len(synonyms) >= 5:
                                return synonyms
    except Exception as e:
        raise ThesaurusAPIError(f"Error parsing Oxford response: {e}")
        
    return synonyms[:5]
