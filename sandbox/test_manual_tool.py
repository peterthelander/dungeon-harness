import google.genai as genai
from google.genai import types

def roll_dice(dice: int):
    print("running dice")
    return {"rolled": 4}

client = genai.Client()
# disable auto_function_calling
chat = client.chats.create(
    model='gemini-3.5-flash',
    config=types.GenerateContentConfig(
        tools=[roll_dice],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )
)
print("Sending message...")
response = chat.send_message_stream("Roll a d20")
for chunk in response:
    print(f"CHUNK: text={chunk.text!r}")
    if chunk.function_calls:
        print("  found FCs:", chunk.function_calls)
        for fc in chunk.function_calls:
            if fc.name == "roll_dice":
                res = roll_dice(**fc.args)
                part = types.Part.from_function_response(name=fc.name, response=res)
                response2 = chat.send_message_stream([part])
                for chunk2 in response2:
                    print(f"CHUNK2: text={chunk2.text!r}")

