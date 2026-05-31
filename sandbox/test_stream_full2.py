import google.genai as genai
from google.genai import types

def roll_dice(dice: int):
    """Roll a dice."""
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(model='gemini-3.5-flash', config=types.GenerateContentConfig(tools=[roll_dice], automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)))
print("Sending message...")
response = chat.send_message("Roll a 20 sided dice for me")
print("Response text:", response.text)
