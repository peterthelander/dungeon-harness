import google.genai as genai
from google.genai import types

def roll_dice(dice: int):
    return {"rolled": 4}

client = genai.Client()
chat = client.chats.create(
    model='gemini-3.5-flash',
    config=types.GenerateContentConfig(
        tools=[roll_dice],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )
)
stream = chat.send_message_stream("Roll a d20")
function_calls = []
for chunk in stream:
    print("CHUNK:", chunk.text, chunk.function_calls)
    if chunk.function_calls:
        function_calls.extend(chunk.function_calls)

if function_calls:
    parts = []
    for fc in function_calls:
        if fc.name == "roll_dice":
            res = roll_dice(**fc.args)
            part = types.Part.from_function_response(name=fc.name, response=res)
            parts.append(part)
    stream2 = chat.send_message_stream(parts)
    for chunk in stream2:
        print("CHUNK2:", repr(chunk.text))
