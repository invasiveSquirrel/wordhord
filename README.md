# Wordhord: Your Personal Language Library

Wordhord is a powerful tool for building and studying massive collections of vocabulary. It works silently in the background, reading through your PDF and EPUB books to create thousands of flashcards for you to study.

## 🌟 What this app does
- **Automatic Vocabulary Building:** Learns from your favorite books and frequency dictionaries.
- **Level-Based Study:** Choose exactly what difficulty you want to practice (from A1 beginner to C2 expert).
- **Study Conversations:** Specifically study the phrases and advice you received during your Panglossia chats.
- **Adjustable Speech:** Every word includes audio that you can slow down to 0.7x speed to hear every detail.

---

## 🚀 How to Download and Install
*You do NOT need to have GitHub installed to use this.*

### 1. Download the Code
1. Scroll to the top of this GitHub page.
2. Click the green button that says **"<> Code"**.
3. Click **"Download ZIP"** at the bottom of the list.
4. Once downloaded, "unzip" or "extract" the folder to your Documents or Desktop.

### 2. Install for Windows
1. Go to [nodejs.org](https://nodejs.org) and click the version that says **"LTS"**. Download and run the installer.
2. Open the folder you unzipped in Step 1.
3. In the address bar at the top of your folder window, type `cmd` and press Enter. 
4. Type `npm install` and press Enter. Wait for it to finish.
5. To run the app, type `npm start`.

### 3. Install for Mac
1. Go to [nodejs.org](https://nodejs.org) and install the **"LTS"** version.
2. Open the **Terminal** (press Command + Space and type "Terminal").
3. Type `cd` followed by a space, then drag the unzipped folder into the Terminal window and press Enter.
4. Type `npm install` and press Enter.
5. Type `npm start` to run.

### 4. Install for Linux
1. Open your terminal in the unzipped folder.
2. Run `./wordhord-launcher.sh`.

---

## 🔑 Setup: Growing your Vocabulary
To let the app automatically generate cards for you:
1. Get a free API key from [Google AI Studio](https://aistudio.google.com/).
2. Place that key in a text file named `wordhord_api.txt` inside this folder.
3. Put any language books (PDF or EPUB) you have into the `vocabulary_sources` folder.
4. The app will automatically start turning those books into flashcards!
