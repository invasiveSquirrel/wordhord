# Wordhord: Your Personal Language Library

Wordhord is a powerful tool for building and studying massive collections of vocabulary. It works silently in the background, reading through your PDF and EPUB books to create thousands of flashcards for you to study.

## 🌍 Supported Languages
Wordhord is optimized for generating and studying:
- **Swedish**
- **German**
- **Finnish**
- **Portuguese**
- **Spanish**
- **Dutch**
- **Scottish Gaelic**

## 🌟 What this app does
- **Automatic Vocabulary Building:** Learns from your favorite books and frequency dictionaries.
- **Level-Based Study:** Choose exactly what difficulty you want to practice (from A1 beginner to C2 expert).
- **Study Conversations:** Specifically study the phrases and advice you received during your Panglossia chats.
- **Adjustable Speech:** Every word includes audio that you can slow down to 0.7x speed to hear every detail.

---

## 🚀 How to Download and Install
*You do NOT need to have GitHub installed to use this.*

### Step 1: Download the Files
1. Scroll to the top of this GitHub page.
2. Look for the green button that says **"<> Code"** and click it.
3. Click **"Download ZIP"** at the bottom of the little menu that appears.

### Step 2: Extract (Unzip) the Folder
Once the download is finished, you need to "unzip" the files before they will work:
- **On Windows:** Right-click the downloaded file and select **"Extract All..."**, then click the **"Extract"** button.
- **On Mac:** Simply double-click the downloaded file. A new, regular folder will appear automatically.
- **On Linux:** Right-click the file and select **"Extract Here"**.

### Step 3: Final Installation
**For Windows:**
1. Install [Node.js](https://nodejs.org) (LTS version).
2. Open your new "extracted" folder.
3. Click the "address bar" at the top of the window, type `cmd` and press Enter. 
4. Type `npm install` and press Enter. Wait for it to finish.
5. To run the app, type `npm start`.

**For Mac:**
1. Install [Node.js](https://nodejs.org).
2. Open the **Terminal** app.
3. Type `cd ` (with a space) and then drag your extracted folder into the terminal window. Press Enter.
4. Type `npm install` and press Enter.
5. Type `npm start` to run.

---

## 🔑 Setup: Growing your Vocabulary
To let the app automatically generate cards for you:
1. Get a free API key from [Google AI Studio](https://aistudio.google.com/).
2. Place that key in a text file named `wordhord_api.txt` inside this folder.
3. Put any language books (PDF or EPUB) you have into the `vocabulary_sources` folder.
4. The app will automatically start turning those books into flashcards!
