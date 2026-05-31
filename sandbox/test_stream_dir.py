import google.genai as genai
from google.genai import types

def roll_dice(dice: int):
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(model='gemini-3.5-flash', config=types.GenerateContentConfig(tools=[roll_dice]))
response = chat.send_message_stream("Roll a 20 sided dice for me")
print("Type of response:", type(response))
for chunk in response:
    pass
print("After loop, text is:", getattr(response, 'text', None))
