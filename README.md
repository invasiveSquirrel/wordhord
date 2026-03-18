# Wordhord: Your Personal Language Library

Wordhord is a powerful tool for building and studying massive vocabulary collections. It works in the background to turn entire books and frequency dictionaries into high-quality flashcards.

## Key Features
- **Massive Vocabulary Building:** Automatically generates thousands of cards from your own PDF and EPUB sources.
- **Level-Based Study:** Filter your cards by CEFR level (A1-C2) or study specific "Expressions" and "Advice" captured from Panglossia.
- **Smart Pronunciation:** Every word includes high-quality audio with speed controls (1.0x to 0.7x).
- **Automated Cleansing:** New cards are automatically formatted and cleansed of errors during generation.

## Installation Instructions

### 🐧 Linux
1. Open your terminal in this folder.
2. Run `./wordhord-launcher.sh` or `./start.sh`.

### 🪟 Windows
1. Install [Node.js](https://nodejs.org).
2. Click **"Code" > "Download ZIP"** on GitHub and unzip it.
3. In the folder, hold **Shift + Right-click** and select **"Open PowerShell window here."**
4. Type `npm install` and press Enter.
5. Type `npm start` to run.

### 🍎 Mac
1. Install [Node.js](https://nodejs.org).
2. Download and unzip the code.
3. Open **Terminal**, drag the folder into the window, and press Enter.
4. Type `npm install` and press Enter.
5. Type `npm start` to run.

## Background Generation Setup
To keep the vocabulary growing:
1. Put your free Gemini API key in a file named `wordhord_api.txt` in this folder.
2. Ensure your source books (PDF/EPUB) are in the `vocabulary_sources` folder.
3. The app will handle the rest!
