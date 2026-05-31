import base64
import google.genai as genai
from google.genai import types

def run():
    client = genai.Client()
    response = client.models.generate_content(
        model='gemini-2.5-flash-image',
        contents="A fantasy landscape",
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )
    )
    print("Success?", response)
run()
