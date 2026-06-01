import google.genai as genai
from google.genai import types
import queue
import threading

q = queue.Queue()

def roll_dice(dice: int):
    q.put({"type": "tool_call", "msg": f"Rolling {dice}"})
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(
    model='gemini-3.5-flash',
    config=types.GenerateContentConfig(tools=[roll_dice])
)

def run_backend():
    try:
        stream = chat.send_message_stream("Roll a 20 sided dice")
        for chunk in stream:
            if chunk.text:
                q.put({"type": "text", "msg": chunk.text})
        q.put({"type": "done"})
    except Exception as e:
        q.put({"type": "error", "msg": str(e)})

t = threading.Thread(target=run_backend)
t.start()
while True:
    try:
        item = q.get(timeout=20)
        print("GOT:", item)
        if item["type"] in ["done", "error"]:
            break
    except queue.Empty:
        print("QUEUE TIMEOUT")
        break
