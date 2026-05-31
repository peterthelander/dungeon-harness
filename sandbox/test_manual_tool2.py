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
response = chat.send_message("Roll a d20")
print("Response FCs:", response.function_calls)
for fc in response.function_calls:
    if fc.name == "roll_dice":
        res = roll_dice(**fc.args)
        part = types.Part.from_function_response(name=fc.name, response=res)
        response2 = chat.send_message([part], stream=True)
        for chunk in response2:
            print("CHUNK:", repr(chunk.text))
