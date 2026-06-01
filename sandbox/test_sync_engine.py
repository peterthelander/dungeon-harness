import google.genai as genai
from google.genai import types
import queue

q = queue.Queue()

def roll_dice(dice: int):
    q.put({"type": "tool_call", "msg": f"Rolling {dice}"})
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(
    model='gemini-3.5-flash',
    config=types.GenerateContentConfig(tools=[roll_dice])
)

def process_action(text):
    dm_text_parts = []
    response = chat.send_message(text)
    
    while not q.empty():
        yield q.get()
        
    yield {"type": "text_chunk", "text": response.text}
    yield {"type": "done"}

for item in process_action("Roll a 20 sided dice"):
    print("YIELDED:", item)
