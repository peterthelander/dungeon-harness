import google.genai as genai
from google.genai import types

def roll_dice(dice: int):
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(model='gemini-3.5-flash', config=types.GenerateContentConfig(tools=[roll_dice]))
print("Sending message...")
response = chat.send_message_stream("Roll a 20 sided dice for me")

for chunk in response:
    print(f"CHUNK 1: {chunk.text!r}")

# Check if there are function calls
history = chat.get_history()
last_msg = history[-1]
for part in last_msg.parts:
    if part.function_call:
        print("Model asked for function call:", part.function_call.name)
        # What if we just call chat.send_message_stream again with the function response?
        response2 = chat.send_message_stream([types.Part.from_function_response(name=part.function_call.name, response={"rolled": 4})])
        for chunk in response2:
            print(f"CHUNK 2: {chunk.text!r}")

