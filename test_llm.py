import asyncio
import os
from langchain_google_genai import ChatGoogleGenerativeAI

def load_google_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY")
    if key: return key
    try:
        api_key_file = "/home/chris/wordhord/wordhord_api.txt"
        with open(api_key_file, "r") as f: return f.read().strip()
    except: return None

async def test():
    key = load_google_api_key()
    if not key:
        print("No API Key found")
        return
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=key)
    try:
        print("Sending test prompt...")
        res = await llm.ainvoke("Say hello")
        print(f"Success: {res.content}")
    except Exception as e:
        print(f"ERROR TYPE: {type(e)}")
        print(f"ERROR MESSAGE: {e}")

if __name__ == "__main__":
    asyncio.run(test())
