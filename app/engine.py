import base64
import logging
import concurrent.futures
import threading
from google.genai import types

from app.model_client import GeminiModelClient
from app.prompts import build_initial_prompt, build_system_instruction
from app.tools import roll_dice


logger = logging.getLogger(__name__)
model_client = GeminiModelClient()
IMAGE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)
IMAGE_SLOTS = threading.BoundedSemaphore(value=4)

FALLBACK_INTRO_TEXT = (
    "The adventure is loaded, and the road ahead is waiting. "
    "Tell me your character's name and what kind of hero you want to play."
)
FALLBACK_SCENE_PROMPT = (
    "Cinematic fantasy tabletop-RPG opening scene: a lone lantern glows beside "
    "a weathered road leading toward distant mountains at dusk, mysterious ruins "
    "on the horizon, dramatic clouds, painterly realism, no words or labels."
)
MAX_SUGGESTIONS = 4
MAX_SUGGESTION_LENGTH = 80


def _normalize_suggestions(raw_suggestions) -> list[str]:
    """Return a small, safe-to-display set of unique action labels."""
    if not isinstance(raw_suggestions, (list, tuple)):
        return []

    suggestions = []
    seen = set()
    for item in raw_suggestions:
        if not isinstance(item, str):
            continue
        suggestion = " ".join(item.split())
        if not suggestion or len(suggestion) > MAX_SUGGESTION_LENGTH:
            continue
        normalized = suggestion.casefold()
        if normalized in seen:
            continue
        suggestions.append(suggestion)
        seen.add(normalized)
        if len(suggestions) == MAX_SUGGESTIONS:
            break
    return suggestions


def _suggestions_in_text(suggestions: list[str], text: str) -> list[str]:
    """Keep only suggestions that can be linked to visible DM text."""
    normalized_text = " ".join(text.split()).casefold()
    return [
        suggestion
        for suggestion in suggestions
        if " ".join(suggestion.split()).casefold() in normalized_text
    ]


def _suggestions_by_message(suggestions: list[str], messages: dict[int, str]) -> dict[int, list[str]]:
    """Associate each suggestion with the latest visible DM message containing it."""
    grouped = {}
    for suggestion in suggestions:
        for message_id in sorted(messages, reverse=True):
            if _suggestions_in_text([suggestion], messages[message_id]):
                grouped.setdefault(message_id, []).append(suggestion)
                break
    return grouped


def _recover_suggestions(chat_session, prompt: str) -> list[str]:
    """Ask the model to identify linkable phrases already shown to the player."""
    try:
        response = model_client.send_message(chat_session, prompt)
        for function_call in _extract_function_calls(response):
            if function_call.name != "suggest_actions":
                continue
            suggestions = _normalize_suggestions(function_call.args.get("suggestions"))
            if not suggestions:
                continue
            model_client.send_message(
                chat_session,
                [
                    types.Part.from_function_response(
                        name="suggest_actions",
                        response={"status": "Action suggestions displayed to the player."},
                    )
                ],
            )
            return suggestions
    except Exception as error:
        logger.warning("engine.suggestions.recovery_failed", extra={"error": str(error)})
    return []


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


def _extract_function_calls(response):
    function_calls = getattr(response, "function_calls", None) or []
    if function_calls:
        return list(function_calls)

    extracted_calls = []
    if (
        response.candidates
        and response.candidates[0].content
        and response.candidates[0].content.parts
    ):
        for part in response.candidates[0].content.parts:
            function_call = getattr(part, "function_call", None)
            if function_call:
                extracted_calls.append(function_call)
    return extracted_calls


def _log_empty_response(response) -> None:
    candidates = getattr(response, "candidates", None) or []
    finish_reasons = [str(getattr(candidate, "finish_reason", None)) for candidate in candidates]
    logger.warning(
        "engine.init.empty_response candidates=%s finish_reasons=%s "
        "prompt_feedback=%r usage_metadata=%r",
        len(candidates),
        finish_reasons,
        getattr(response, "prompt_feedback", None),
        getattr(response, "usage_metadata", None),
    )


def _async_image_wrapper(visual_description: str):
    try:
        return draw_scene(visual_description)
    finally:
        IMAGE_SLOTS.release()


def draw_scene(visual_description: str) -> str | None:
    """Generate a scene image and return it as a data URL."""
    logger.info("scene.render.start")
    image_result = model_client.generate_image(visual_description)
    if image_result.candidates and image_result.candidates[0].content and image_result.candidates[0].content.parts:
        for part in image_result.candidates[0].content.parts:
            if part.inline_data:
                raw_bytes = part.inline_data.data
                b64_img = base64.b64encode(raw_bytes).decode("utf-8")
                mime_type = part.inline_data.mime_type or "image/jpeg"
                logger.info("scene.render.complete")
                return f"data:{mime_type};base64,{b64_img}"
    logger.info("scene.render.complete")
    return None


def draw_scene_tool(visual_description: str) -> dict:
    """Request a visual of the current scene for the player canvas."""
    # This callable defines the schema exposed to Gemini. Rendering itself is
    # performed by the server-side tool dispatcher, which owns session state.
    return {"status": "Scene rendering request accepted."}


draw_scene_tool.__name__ = "draw_scene"


def suggest_actions_tool(suggestions: list[str]) -> dict:
    """Offer a few short, spoiler-free action prompts for the player UI."""
    return {"status": "Action suggestions accepted."}


suggest_actions_tool.__name__ = "suggest_actions"


def upload_pdf_and_init(temp_path: str, filename: str, session_state: dict):
    """Uploads PDF to Gemini and initializes the game chat session."""
    logger.info("engine.init.upload.start", extra={"upload_filename": filename})
    uploaded_pdf = model_client.upload_file(temp_path)
    uploaded_pdf = model_client.wait_for_file_processing(uploaded_pdf)
    session_state["latest_pdf"] = uploaded_pdf
    session_state["chat_session"] = model_client.create_chat_session(
        system_instruction=build_system_instruction(),
        tools=[roll_dice, draw_scene_tool, suggest_actions_tool],
    )

    current_response = model_client.send_message(
        session_state["chat_session"], build_initial_prompt(uploaded_pdf)
    )
    dm_text = ""
    image_data = None
    suggestions = []

    while True:
        try:
            extracted_text, extracted_image = _extract_text_and_image(current_response)
            dm_text += extracted_text
            if extracted_image:
                image_data = extracted_image
        except Exception as e:
            logger.warning("engine.init.extract.failed", extra={"error": str(e)})

        function_calls = _extract_function_calls(current_response)
        if not function_calls:
            if not dm_text.strip():
                _log_empty_response(current_response)
            break

        tool_responses = []
        for fc in function_calls:
            logger.info("engine.init.tool", extra={"tool_name": fc.name})
            if fc.name == "roll_dice":
                res = roll_dice(**fc.args)
                res.pop("ui_message", "")
            elif fc.name == "draw_scene":
                visual_description = fc.args.get("visual_description", "")
                image_data = draw_scene(visual_description=visual_description)
                res = {"status": "Scene successfully rendered on the player's canvas."}
            elif fc.name == "suggest_actions":
                suggestions = _normalize_suggestions(fc.args.get("suggestions"))
                res = {"status": "Matching phrases will be linked in the player UI."}
            else:
                res = {"error": f"Tool {fc.name} not implemented."}

            tool_responses.append(types.Part.from_function_response(name=fc.name, response=res))

        current_response = model_client.send_message(session_state["chat_session"], tool_responses)

    if not dm_text.strip():
        logger.warning("engine.init.empty_intro")
        dm_text = FALLBACK_INTRO_TEXT

    if image_data is None:
        try:
            image_data = draw_scene(FALLBACK_SCENE_PROMPT)
        except Exception:
            logger.exception("engine.init.fallback_scene_failed")

    suggestions = _suggestions_in_text(suggestions, dm_text)
    if not suggestions:
        recovered_suggestions = _recover_suggestions(
            session_state["chat_session"],
            "The opening invitation is already shown. Call suggest_actions now with 2 or 3 "
            "natural readiness phrases that appear verbatim in that text. Do not write any "
            "narrative or call another tool.",
        )
        suggestions = _suggestions_in_text(recovered_suggestions, dm_text)

    return dm_text, image_data, suggestions


def process_action(player_text: str, session_state: dict):
    """The core execution loop for driving a player action synchronously as a pure generator."""
    chat_session = session_state.get("chat_session")
    if not chat_session:
        yield {"type": "error", "error": "Engine not initialized. Please upload a PDF first."}
        return

    try:
        player_preview = " ".join(player_text.split())[:240]
        logger.info(
            "engine.action.start text_length=%s text_preview=%r",
            len(player_text),
            player_preview,
        )
        current_input = player_text
        dm_text_full = ""
        pending_image_jobs = []
        stream_chunk_count = 0
        function_call_count = 0
        finish_reasons = []
        latest_suggestions = None
        message_id = 0
        message_texts = {message_id: ""}

        while True:
            response = model_client.send_message_stream(chat_session, current_input)
            function_calls = []

            for chunk in response:
                stream_chunk_count += 1
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if getattr(part, "text", None):
                            dm_text_full += part.text
                            message_texts[message_id] += part.text
                            yield {"type": "text_chunk", "text": part.text, "message_id": message_id}

                for candidate in getattr(chunk, "candidates", None) or []:
                    if getattr(candidate, "finish_reason", None) is not None:
                        finish_reasons.append(str(candidate.finish_reason))

                chunk_function_calls = _extract_function_calls(chunk)
                function_calls.extend(chunk_function_calls)
                function_call_count += len(chunk_function_calls)

                completed_jobs = [job for job in pending_image_jobs if job["future"].done()]
                for job in completed_jobs:
                    pending_image_jobs.remove(job)
                    try:
                        image_data = job["future"].result()
                        if image_data:
                            yield {"type": "image", "image_data": image_data}
                    except Exception as e:
                        logger.warning("scene.render.async_failed", extra={"error": str(e)})
                        yield {"type": "tool_call", "message": ">> **System**: Scene generation failed."}

            if not function_calls:
                break

            tool_responses = []
            emitted_tool_call = False
            for fc in function_calls:
                if fc.name == "roll_dice":
                    res = roll_dice(**fc.args)
                    ui_message = res.pop("ui_message", ">> **System**: Rolling dice...")
                    yield {"type": "tool_call", "message": ui_message}
                    emitted_tool_call = True
                elif fc.name == "draw_scene":
                    visual_description = fc.args.get("visual_description", "")
                    if IMAGE_SLOTS.acquire(blocking=False):
                        future = IMAGE_EXECUTOR.submit(_async_image_wrapper, visual_description)
                        pending_image_jobs.append({"future": future, "visual_description": visual_description})
                        res = {"status": "Scene generation started asynchronously and will be displayed when ready."}
                    else:
                        res = {"status": "Scene generation skipped because the renderer is busy."}
                elif fc.name == "suggest_actions":
                    latest_suggestions = _normalize_suggestions(fc.args.get("suggestions"))
                    res = {"status": "Action suggestions displayed to the player."}
                else:
                    res = {"error": f"Tool {fc.name} not implemented."}
                    yield {"type": "tool_call", "message": f">> **System**: Called unexpected tool `{fc.name}`"}
                    emitted_tool_call = True

                tool_responses.append(types.Part.from_function_response(name=fc.name, response=res))

            current_input = tool_responses
            if emitted_tool_call:
                message_id += 1
                message_texts[message_id] = ""

        for job in list(pending_image_jobs):
            try:
                image_data = job["future"].result()
                if image_data:
                    yield {"type": "image", "image_data": image_data}
            except Exception as e:
                logger.warning("scene.render.finalize_failed", extra={"error": str(e)})
                yield {"type": "tool_call", "message": ">> **System**: Scene generation failed."}

        if not dm_text_full and function_call_count == 0:
            logger.warning(
                "engine.action.empty_response chunks=%s finish_reasons=%s",
                stream_chunk_count,
                finish_reasons,
            )
            recovery_prompt = (
                "Continue the tabletop-RPG conversation now. The player just said "
                f"{player_text!r}. Give a concrete, short Dungeon Master response based "
                "on the adventure context. Do not mention this recovery instruction and "
                "do not call tools in this response."
            )
            recovery_response = model_client.send_message(chat_session, recovery_prompt)
            recovery_text, _ = _extract_text_and_image(recovery_response)
            if recovery_text:
                dm_text_full = recovery_text
                message_texts[message_id] = recovery_text
                logger.info("engine.action.recovery_succeeded text_length=%s", len(recovery_text))
                yield {"type": "text_chunk", "text": recovery_text, "message_id": message_id}
            else:
                logger.warning("engine.action.recovery_empty")
        else:
            logger.info(
                "engine.action.complete text_length=%s chunks=%s function_calls=%s",
                len(dm_text_full),
                stream_chunk_count,
                function_call_count,
            )

        suggestions_by_message = _suggestions_by_message(latest_suggestions or [], message_texts)
        if not suggestions_by_message:
            recovered_suggestions = _recover_suggestions(
                chat_session,
                "Your immediately preceding Dungeon Master response is already shown. Call "
                "suggest_actions now with 2 to 4 natural, spoiler-free action phrases that "
                "appear verbatim in that response. Do not write any narrative or call another tool.",
            )
            suggestions_by_message = _suggestions_by_message(recovered_suggestions, message_texts)
        for suggestion_message_id, items in suggestions_by_message.items():
            yield {"type": "suggestions", "items": items, "message_id": suggestion_message_id}
        yield {"type": "done"}
    except Exception as e:
        logger.exception("engine.action.failed", extra={"error": str(e)})
        yield {"type": "error", "error": "Action processing failed."}
