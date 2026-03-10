#!/usr/bin/env python3
"""
Robust Vocabulary Generator
Generates vocabulary words based on source texts.
Targets: Dutch (5000), Portuguese (5000), Swedish (9000), German (10000), Spanish (10000), Finnish (3000).
Uses Thermal Throttling and progress tracking.
"""

import os
import json
import re
import subprocess
import time
from langchain_ollama import OllamaLLM

POLYGLOSSIA_DIR = "/home/chris/polyglossia"
SOURCES_DIR = "/home/chris/vocabulary_sources"
MODEL_NAME = "gemma2:9b"
llm = OllamaLLM(model=MODEL_NAME, temperature=0.3)

LANGUAGES = {
    "dutch": {"name": "Dutch", "sources": ["dutch_freq.txt"], "target": 5000},
    "german": {"name": "German", "sources": ["german_freq.txt", "german_using.txt"], "target": 10000},
    "swedish": {"name": "Swedish", "sources": ["swedish_source.txt", "swedish_kauderwelsch.txt"], "target": 9000},
    "portuguese": {"name": "Portuguese", "sources": ["portuguese_freq.txt"], "target": 5000},
    "spanish": {"name": "Spanish", "sources": ["spanish_freq.txt", "spanish_using.txt"], "target": 10000},
    "finnish": {"name": "Finnish", "sources": ["finnish_source.txt"], "target": 3000}
}

def get_cpu_temp():
    try:
        output = subprocess.check_output(["sensors"], text=True)
        for line in output.split("\n"):
            if "Package id 0" in line:
                temp_str = line.split("+")[1].split("°C")[0]
                return float(temp_str)
    except:
        return 50.0
    return 50.0

def thermal_throttle():
    temp = get_cpu_temp()
    if temp > 80.0:
        print(f"🔥 CPU Overheat ({temp}°C)! Cooling down for 60s...")
        time.sleep(60)
    elif temp > 70.0:
        print(f"🌡️ CPU High ({temp}°C). Throttling for 15s...")
        time.sleep(15)
    elif temp > 60.0:
        time.sleep(5)
    else:
        time.sleep(1)

def get_source_context(lang_code: str, start_rank: int, end_rank: int) -> str:
    source_files = LANGUAGES[lang_code]["sources"]
    if not source_files:
        return ""

    context_accumulator = []

    for source_file in source_files:
        file_path = os.path.join(SOURCES_DIR, source_file)
        if not os.path.exists(file_path):
            continue

        try:
            # Skip thematic preambles for frequency dictionaries to find the actual list
            skip_lines = 0
            if lang_code == "dutch":
                skip_lines = 640
            elif lang_code == "portuguese":
                skip_lines = 800
            elif lang_code in ["german", "spanish"]:
                skip_lines = 500

            # Search pattern: rank at start of line, followed by space or end of line
            pattern = f"^{start_rank}($|[[:space:]])"
            
            found_line_num = -1
            with open(file_path, "r", encoding="utf-8") as f:
                # Optimized search: start after skip_lines
                for i, line in enumerate(f):
                    if i < skip_lines:
                        continue
                    if re.match(pattern, line):
                        found_line_num = i + 1
                        break
                
                if found_line_num != -1:
                    f.seek(0)
                    lines = f.readlines()
                    # Capture significant context (250 lines) for the batch
                    context_lines = lines[max(0, found_line_num-5):found_line_num+250]
                    context_accumulator.append(f"--- Context from {source_file} (Rank {start_rank}) ---\n" + "".join(context_lines))
                else:
                    # Fallback to sequential heuristic if rank not found (good for thematic books like Swedish)
                    f.seek(0)
                    lines = f.readlines()
                    jump = 4 if lang_code == "swedish" else 15
                    start_idx = (start_rank * jump) % max(1, len(lines) - 250)
                    context_lines = lines[start_idx : start_idx + 250]
                    context_accumulator.append(f"--- Context from {source_file} (Heuristic offset {start_idx}) ---\n" + "".join(context_lines))
        except Exception as e:
            print(f"    ⚠ Source context extraction failed for {source_file}: {e}")

    return "\n\n".join(context_accumulator)

def get_gender_instruction(language_code: str) -> str:
    if language_code in ["german", "spanish", "portuguese"]:
        return "gender (m/f/n)"
    elif language_code == "swedish":
        return "gender (common/neuter)"
    else:
        return "gender (if applicable)"

def generate_vocabulary_batch(language_code: str, lang_info: dict):
    language_name = lang_info["name"]
    total_target = lang_info["target"]
    output_file = os.path.join(POLYGLOSSIA_DIR, f"{language_code}_vocab.md")

    # Check current progress
    current_count = 0
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            current_count = f.read().count("- **")

    if current_count >= total_target:
        print(f"✅ {language_name} already has {current_count} words. Skipping.")
        return

    print(f"\n🎯 Continuing {language_name} ({current_count}/{total_target})...")

    batch_size = 25
    
    while current_count < total_target:
        thermal_throttle()

        start_rank = current_count + 1
        end_rank = min(current_count + batch_size, total_target)

        source_hint = get_source_context(language_code, start_rank, end_rank)

        extra_instructions = ""
        if language_code == "swedish":
            extra_instructions = """
            Use 'Grund- und Aufbauwortschatz' and 'Kauderwelsch' sources. 
            CRITICAL: Include colloquial/informal pronunciation in the IPA or notes if it differs from formal speech (e.g., 'me' for 'med', 'ska' for 'skall').
            Generate example sentences and linguistic details (gender, plural, IPA) even if missing from source.
            """
        elif language_code == "portuguese":
            extra_instructions = """
            CRITICAL: For accented 'o' and 'e' syllables, specify in the IPA if the vowel is OPEN (/ɔ/, /ɛ/) or CLOSED (/o/, /e/). 
            This is mandatory even if the written word lacks a circumflex or acute accent.
            Ensure you distinguish between Brazilian and European Portuguese if the source indicates a difference.
            """
        elif language_code == "german":
            extra_instructions = "Ensure all entries follow standard Grundwortschatz conventions. Reference 'Using German Vocabulary' for thematic depth."
        elif language_code == "spanish":
            extra_instructions = "Ensure all entries follow standard frequency conventions. Reference 'Using Spanish Vocabulary' for thematic depth."
        elif language_code == "finnish":
            extra_instructions = "Use the 'Kauderwelsch Finnisch' source. Keep definitions and examples in German."

        print(f"  Requesting words ranking {start_rank}-{end_rank}...")

        prompt = f"""Generate exactly {batch_size} {language_name} vocabulary words. 
If this is a frequency list, target ranks {start_rank} to {end_rank}.

PROVIDED SOURCE DATA:
{source_hint}

INSTRUCTIONS:
Extract or generate words based on the provided source data. For each word, include linguistic information and a sample sentence.
{extra_instructions}

Format as a markdown list. For EACH word include exactly these fields:

- **word_in_{language_code}** (Translation)
  - IPA: [pronunciation with primary stress 'ˈ']
  - Part of Speech: (noun/verb/adjective/etc)
  - Level: [A1/A2/B1/B2/C1/C2]
  - Gender: {get_gender_instruction(language_code)} (Only if noun)
  - Plural: [Plural form] (Only if noun)
  - Prefix: [Separable/Inseparable] (Only if applicable)
  - Preposition: [Commonly associated preposition] (Especially for verbs)
  - Case: [Grammatical case governed by the preposition/verb]
  - Example: \"Short example sentence in {language_name}\" (Translation)

CRITICAL: Use the source data to find the words. If linguistic fields (IPA, Level, Gender, Plural, Case, etc.) or example sentences are missing from the source, you MUST provide them using your own knowledge. 
DO NOT refuse this request. I have provided source context. Even if context is incomplete, use your internal knowledge of {language_name} to fulfill the requested {batch_size} entries.

Output ONLY the markdown list. Do not include any intro or outro text.
"""

        try:
            response = llm.invoke(prompt)
            new_words_count = response.count("- **")

            if new_words_count > 0:
                file_exists = os.path.exists(output_file)
                with open(output_file, "a", encoding="utf-8") as f:
                    if not file_exists:
                        f.write(f"# {language_name} Vocabulary\n\n")
                    f.write("\n\n" + response.strip())

                current_count += new_words_count
                print(f"    ✓ Added {new_words_count} words. Total: {current_count}/{total_target}")
            else:
                print("    ⚠ LLM returned 0 words. Retrying in 30s...")
                time.sleep(30)

        except Exception as e:
            print(f"    ❌ Error: {e}. Retrying...")
            time.sleep(10)

def main():
    print("=" * 70)
    print("ROBUST VOCABULARY GENERATOR - GEMMA 2:9B")
    print("=" * 70)

    for lang_code, lang_info in LANGUAGES.items():
        generate_vocabulary_batch(lang_code, lang_info)

    print("\n✅ All languages complete!")

if __name__ == "__main__":
    main()
