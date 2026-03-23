import csv
import json
import os

def parse_plain_text(file_path):
    """
    Parses a simple plain text file where each line is a word.
    Returns a list of words.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def parse_csv(file_path, term_col='term'):
    """
    Parses a CSV file containing vocabulary.
    Returns a list of dictionaries.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    vocab = []
    with open(file_path, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if term_col in row:
                vocab.append(row)
            else:
                # If term_col not found, just return the whole row
                vocab.append(row)
    return vocab

def parse_json(file_path):
    """
    Parses a JSON file containing vocabulary.
    Expects a list of objects or a dict with a list of words.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        # try to find a common key like 'words' or 'vocabulary'
        for key in ['words', 'vocabulary', 'terms', 'data']:
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data] # Fallback
    return []
