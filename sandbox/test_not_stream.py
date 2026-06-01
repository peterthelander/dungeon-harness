import google.genai as genai
from google.genai import types

def roll_dice(dice: int):
    print(f"Rolling {dice}")
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(
    model='gemini-3.5-flash',
    config=types.GenerateContentConfig(tools=[roll_dice])
)

resp = chat.send_message("Roll a 20 sided dice")
print("TEXT:", repr(resp.text))
