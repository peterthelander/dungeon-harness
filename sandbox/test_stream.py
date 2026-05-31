import google.genai as genai
from google.genai import types
import sys

client = genai.Client()
chat = client.chats.create(model='gemini-3.5-flash')
response = chat.send_message_stream("Write a 50 word story about a cat")
for chunk in response:
    print(f"CHUNK: {chunk.text}")
