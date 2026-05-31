import google.genai as genai
import time
client = genai.Client()
with open("test.txt", "w") as f: f.write("Hello")
f = client.files.upload(file="test.txt")
print(f.state)
print(dir(f.state))
print(f.state.name)
