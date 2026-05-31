import google.genai as genai
from google.genai import types

def roll_dice(dice: int):
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(model='gemini-3.5-flash', config=types.GenerateContentConfig(tools=[roll_dice]))
response = chat.send_message_stream("Roll a d20")
for _ in response:
    pass

for m in chat.get_history():
    print("ROLE:", m.role, "PARTS:", [p for p in m.parts])
