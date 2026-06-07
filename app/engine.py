import base64
import logging
import concurrent.futures
from google.genai import types

from app.model_client import GeminiModelClient
from app.prompts import build_initial_prompt, build_system_instruction
from app.tools import roll_dice


logger = logging.getLogger(__name__)
model_client = GeminiModelClient()
IMAGE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _extract_text_and_image(current_response):
    dm_text = ""
    image_data = None
    if (
        current_response.candidates
        and current_response.candidates[0].content
        and current_response.candidates[0].content.parts
    ):
        for part in current_response.candidates[0].content.parts:
            if getattr(part, "text", None):
                dm_text += part.text
            if getattr(part, "inline_data", None) and part.inline_data.data:
                raw_bytes = part.inline_data.data
                b64_img = base64.b64encode(raw_bytes).decode("utf-8")
                mime_type = part.inline_data.mime_type or "image/jpeg"
                image_data = f"data:{mime_type};base64,{b64_img}"
    return dm_text, image_data


def draw_scene(visual_description: str, session_state: dict) -> dict:
    """Generate a scene image from a direct visual description prompt."""
    logger.info("scene.render.start")
    image_result = model_client.generate_image(visual_description)
    if image_result.candidates and image_result.candidates[0].content and image_result.candidates[0].content.parts:
        for part in image_result.candidates[0].content.parts:
            if part.inline_data:
                raw_bytes = part.inline_data.data
                b64_img = base64.b64encode(raw_bytes).decode("utf-8")
                mime_type = part.inline_data.mime_type or "image/jpeg"
                session_state["latest_scene_image_data"] = f"data:{mime_type};base64,{b64_img}"
                break
    logger.info("scene.render.complete")
    return {"status": "Scene successfully rendered on the player's canvas."}


def upload_pdf_and_init(temp_path: str, filename: str, session_state: dict):
    """Uploads PDF to Gemini and initializes the game chat session."""
    logger.info("engine.init.upload.start", extra={"filename": filename})
    uploaded_pdf = model_client.upload_file(temp_path)
    uploaded_pdf = model_client.wait_for_file_processing(uploaded_pdf)
    session_state["latest_pdf"] = uploaded_pdf
    session_state["chat_session"] = model_client.create_chat_session(
        system_instruction=build_system_instruction(),
        tools=[roll_dice, draw_scene],
    )

    current_response = model_client.send_message(
        session_state["chat_session"], build_initial_prompt(uploaded_pdf)
    )
    dm_text = ""
    image_data = None

    while True:
        try:
            extracted_text, extracted_image = _extract_text_and_image(current_response)
            dm_text += extracted_text
            if extracted_image:
                image_data = extracted_image
        except Exception as e:
            logger.warning("engine.init.extract.failed", extra={"error": str(e)})

        function_calls = getattr(current_response, "function_calls", None) or []
        if not function_calls:
            break

        tool_responses = []
        for fc in function_calls:
            logger.info("engine.init.tool", extra={"tool_name": fc.name})
            if fc.name == "roll_dice":
                res = roll_dice(**fc.args)
                res.pop("ui_message", "")
            elif fc.name == "draw_scene":
                visual_description = fc.args.get("visual_description", "")
                res = draw_scene(visual_description=visual_description, session_state=session_state)
                img = session_state.pop("latest_scene_image_data", None)
                if img:
                    image_data = img
            else:
                res = {"error": f"Tool {fc.name} not implemented."}

            tool_responses.append(types.Part.from_function_response(name=fc.name, response=res))

        current_response = model_client.send_message(session_state["chat_session"], tool_responses)

    if not dm_text.strip():
        logger.warning("engine.init.empty_intro")
        dm_text = "Welcome to the adventure! I am your AI Game Master. What do you do?"

    return dm_text, image_data


def process_action(player_text: str, session_state: dict):
    """The core execution loop for driving a player action synchronously as a pure generator."""
    chat_session = session_state.get("chat_session")
    if not chat_session:
        yield {"type": "error", "error": "Engine not initialized. Please upload a PDF first."}
        return

    try:
        logger.info("engine.action.start")
        current_input = player_text
        dm_text_full = ""
        pending_image_jobs = []

        def _async_image_wrapper(visual_description: str, state: dict):
            draw_scene(visual_description, state)
            return state.pop("latest_scene_image_data", None)

        while True:
            response = model_client.send_message_stream(chat_session, current_input)
            function_calls = []

            for chunk in response:
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if getattr(part, "text", None):
                            dm_text_full += part.text
                            yield {"type": "text_chunk", "text": part.text}

                if chunk.function_calls:
                    function_calls.extend(chunk.function_calls)

                completed_jobs = [job for job in pending_image_jobs if job["future"].done()]
                for job in completed_jobs:
                    pending_image_jobs.remove(job)
                    try:
                        image_data = job["future"].result()
                        if image_data:
                            yield {"type": "image", "image_data": image_data}
                    except Exception as e:
                        yield {"type": "tool_call", "message": f">> **System**: Scene generation failed: {str(e)}"}

            if not function_calls:
                break

            tool_responses = []
            for fc in function_calls:
                if fc.name == "roll_dice":
                    res = roll_dice(**fc.args)
                    ui_message = res.pop("ui_message", ">> **System**: Rolling dice...")
                    yield {"type": "tool_call", "message": ui_message}
                elif fc.name == "draw_scene":
                    visual_description = fc.args.get("visual_description", "")
                    future = IMAGE_EXECUTOR.submit(_async_image_wrapper, visual_description, session_state)
                    pending_image_jobs.append({"future": future, "visual_description": visual_description})
                    res = {"status": "Scene generation started asynchronously and will be displayed when ready."}
                else:
                    res = {"error": f"Tool {fc.name} not implemented."}
                    yield {"type": "tool_call", "message": f">> **System**: Called unexpected tool `{fc.name}`"}

                tool_responses.append(types.Part.from_function_response(name=fc.name, response=res))

            current_input = tool_responses

        for job in list(pending_image_jobs):
            try:
                image_data = job["future"].result()
                if image_data:
                    yield {"type": "image", "image_data": image_data}
            except Exception as e:
                yield {"type": "tool_call", "message": f">> **System**: Scene generation failed: {str(e)}"}

        logger.info("engine.action.complete", extra={"text_length": len(dm_text_full)})
        yield {"type": "done"}
    except Exception as e:
        logger.exception("engine.action.failed", extra={"error": str(e)})
        yield {"type": "error", "error": "Action processing failed."}
