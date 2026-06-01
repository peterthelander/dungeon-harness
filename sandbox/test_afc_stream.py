import google.genai as genai
from google.genai import types
import queue
import threading

def roll_dice(dice: int):
    print("EXECUTING ROLL DICE NATIVELY")
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(
    model='gemini-3.5-flash',
    config=types.GenerateContentConfig(tools=[roll_dice])
)

print("STARTING STREAM")
for chunk in chat.send_message_stream("Roll a twenty sided dice."):
    print("CHUNK:", repr(chunk.text))
