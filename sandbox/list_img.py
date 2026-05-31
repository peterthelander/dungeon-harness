import google.genai as genai

client = genai.Client()
for model in client.models.list():
    if 'generate_images' in str(model.supported_actions) or 'predict' in str(model.supported_actions) or 'generate' in model.name:
        print(model.name)
