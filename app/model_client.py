import time
import google.genai as genai
from google.genai import types


class GeminiModelClient:
    def __init__(self, client=None):
        self.client = client or genai.Client()

    def upload_file(self, temp_path: str):
        return self.client.files.upload(file=temp_path)

    def wait_for_file_processing(self, uploaded_pdf, poll_seconds: int = 2):
        while uploaded_pdf.state.name == "PROCESSING":
            time.sleep(poll_seconds)
            uploaded_pdf = self.client.files.get(name=uploaded_pdf.name)
        if uploaded_pdf.state.name == "FAILED":
            raise ValueError(f"Gemini failed to process the PDF: {uploaded_pdf.name}")
        return uploaded_pdf

    def create_chat_session(self, system_instruction: str, tools):
        return self.client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )

    def send_message(self, chat_session, contents):
        return chat_session.send_message(contents)

    def send_message_stream(self, chat_session, contents):
        return chat_session.send_message_stream(contents)

    def generate_image(self, visual_description: str):
        return self.client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=visual_description.strip(),
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
