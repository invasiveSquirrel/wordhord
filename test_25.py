import asyncio
import os
from langchain_google_genai import ChatGoogleGenerativeAI

def load_key():
    api_key_file = os.path.expanduser("~/wordhord/wordhord_api.txt")
    with open(api_key_file, "r") as f: return f.read().strip()

async def test():
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=load_key())
        response = await llm.ainvoke("Say 'Gemini 2.5 Flash is active'")
        print(response.content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
