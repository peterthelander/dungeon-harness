import google.genai as genai
from google.genai import types

def roll_dice(dice: int):
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(model='gemini-3.5-flash', config=types.GenerateContentConfig(tools=[roll_dice]))
print("Sending message...")
response = chat.send_message_stream("Roll a 20 sided dice for me and tell me the result")
for chunk in response:
    print(f"CHUNK: text={chunk.text!r}")
    if chunk.function_calls:
        print(f"FC: {chunk.function_calls}")
print("Final chat history length:", len(chat.get_history()))
