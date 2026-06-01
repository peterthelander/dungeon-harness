import google.genai as genai
from google.genai import types
import queue
import threading

def roll_dice(dice: int):
    q.put({"type": "tool_call", "msg": f"Rolling {dice}"})
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(
    model='gemini-3.5-flash',
    config=types.GenerateContentConfig(tools=[roll_dice])
)

q = queue.Queue()

def process_action(text):
    dm_text_parts = []
    
    def background():
        try:
            stream = chat.send_message_stream(text)
            for chunk in stream:
                chunk_text = chunk.text or ""
                if chunk_text:
                    q.put({"type": "text_chunk", "text": chunk_text})
            q.put({"type": "done_internal"})
        except Exception as e:
            q.put({"type": "error", "error": str(e)})

    t = threading.Thread(target=background)
    t.start()
    
    while True:
        item = q.get()
        if item["type"] == "done_internal":
            break
        yield item

for item in process_action("Roll a 20 sided dice"):
    print("YIELDED:", item)
