# Vocabulary Generation Instructions

This document outlines the requirements and processes for generating high-quality vocabulary lists for the Wordhord application.

## Core Requirements

For each vocabulary entry, the following fields are mandatory:

- **Word in Target Language** (with Translation)
- **IPA Pronunciation**: Must include primary stress (ˈ).
- **Part of Speech**: (noun, verb, adjective, etc.)
- **Gender**: 
    - Dutch/German: m/f/n
    - Spanish/Portuguese: m/f
    - Swedish: common/neuter
- **Plural Form**: (Required for nouns)
- **Prefix**: (Separable/Inseparable, for verbs)
- **Preposition & Case**: (Required for verbs/adjectives that govern specific cases)
- **Example Sentence**: A short, contextually accurate sentence in the target language with its translation.

## Language-Specific Rules

### Portuguese
- **Vowel Quality**: In accented syllables (and key unaccented ones), distinguish between open vowels (/ɔ/, /ɛ/) and closed vowels (/o/, /e/). This is required even if not explicitly marked by a written accent.
- **Dialects**: Ensure consistency with the source's dialect (Brazilian vs. European).

### Swedish
- **Colloquialism**: Include informal or colloquial pronunciations (e.g., 'me' for 'med', 'ska' for 'skall') in the IPA or as a note if they differ significantly from formal speech.

### Finnish
- **Definitions**: Keep definitions and examples in German (per current source requirements).

## Process

The `generate_vocabulary_improved.py` script uses a local LLM (Gemma 2 9B via Ollama) to process source texts from `/home/chris/vocabulary_sources/`. 

- **Thermal Throttling**: The script monitors CPU temperature to prevent overheating.
- **Progress Tracking**: It tracks progress in `/home/chris/polyglossia/*.md` and resumes where it left off.
- **Source Context**: It extracts relevant ranks or sections from frequency dictionaries and thematic books to provide context to the LLM.

## Targets

Current target entry counts for complete coverage:
- **Dutch**: 5,000 entries
- **Portuguese**: 5,000 entries
- **Swedish**: 9,000 entries
- **German**: 10,000 entries
- **Spanish**: 10,000 entries
- **Finnish**: 3,000 entries
