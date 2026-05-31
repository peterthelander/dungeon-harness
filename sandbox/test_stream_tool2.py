import google.genai as genai
from google.genai import types

def roll_dice(dice: int):
    """Roll a dice."""
    print("INSIDE ROLL DICE!")
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(model='gemini-3.5-flash', config=types.GenerateContentConfig(tools=[roll_dice]))
response = chat.send_message_stream("Roll a 20 sided dice for me")
for chunk in response:
    print("NEW CHUNK:")
    print("  text:", chunk.text)
    try:
        print("  parts:", chunk.parts)
    except:
        pass
