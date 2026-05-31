import google.genai as genai
from google.genai import types

client = genai.Client()
try:
    image_result = client.models.generate_images(
        model='imagen-4.0-fast-generate-001',
        prompt='A fantasy TTRPG landscape',
        config=types.GenerateImagesConfig(
            number_of_images=1,
            output_mime_type="image/jpeg",
            aspect_ratio="16:9"
        )
    )
    print("Success with imagen-4.0-fast-generate-001!")
except Exception as e:
    print(f"Error with imagen-4.0-fast-generate-001: {e}")
