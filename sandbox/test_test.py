import google.genai as genai
from google.genai import types

def roll_dice(dice: int):
    """Roll a dice."""
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(model='gemini-3.5-flash', config=types.GenerateContentConfig(tools=[roll_dice]))

for chunk in chat.send_message_stream("Roll a 20 sided dice for me"):
    print("CHUNK text:", repr(chunk.text), "FC:", getattr(chunk, "function_calls", None))
