#!/usr/bin/env python3
import argparse
import sys
import os

# Add backend to path so we can import synonyms
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from synonyms import get_synonyms

def main():
    parser = argparse.ArgumentParser(description="Fetch synonyms for a given word.")
    parser.add_argument("word", help="The word to find synonyms for")
    parser.add_argument("--lang", default="en", help="ISO 639-1 language code (default: en)")
    parser.add_argument("--thesaurus-source", choices=["dm", "mw", "ox"], default="dm", help="Thesaurus API source: Datamuse (dm), Merriam-Webster (mw), Oxford (ox)")
    
    args = parser.parse_args()
    
    synonyms = get_synonyms(args.word, args.lang, args.thesaurus_source)
    
    if not synonyms:
        print(f"No synonyms found for '{args.word}' using source '{args.thesaurus_source}'.")
    else:
        print(f"Top {len(synonyms)} synonyms for '{args.word}':")
        for i, syn in enumerate(synonyms, 1):
            print(f"{i}. {syn}")

if __name__ == "__main__":
    main()
