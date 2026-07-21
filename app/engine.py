import base64
import logging

from google.genai import types

from app.errors import PUBLIC_USAGE_LIMIT_MESSAGE, is_gemini_usage_limit_error
from app.model_client import GeminiModelClient
from app.prompts import build_initial_prompt, build_system_instruction
from app.scenes import SceneRenderer
from app.state import SessionState
from app.tool_dispatch import ToolDispatcher, draw_scene_tool
from app.tools import roll_dice


logger = logging.getLogger(__name__)
model_client = GeminiModelClient()
scene_renderer = SceneRenderer(model_client)
tool_dispatcher = ToolDispatcher(scene_renderer)

FALLBACK_INTRO_TEXT = (
    "The adventure is loaded, and the road ahead is waiting. "
    "Tell me your character's name and what kind of hero you want to play."
)
FALLBACK_SCENE_PROMPT = (
    "Cinematic fantasy tabletop-RPG opening scene: a lone lantern glows beside "
    "a weathered road leading toward distant mountains at dusk, mysterious ruins "
    "on the horizon, painterly realism, no words or labels."
)
TURN_FINAL_TOOL_NAMES = {"draw_scene"}


def _opening_scene_prompt(introduction: str) -> str:
    return (
        "Create a cinematic fantasy tabletop-RPG opening illustration grounded in "
        "the scene below. Depict its specific location, environment, focal subject, "
        "danger, lighting, and atmosphere. Do not include interface elements, written "
        "words, labels, captions, or choice text. Painterly realism.\n\n"
        f"Opening scene:\n{introduction.strip()}"
    )


def _tool_calls_only_finish_visible_turn(function_calls) -> bool:
    return bool(function_calls) and all(
        getattr(function_call, "name", None) in TURN_FINAL_TOOL_NAMES
        for function_call in function_calls
    )


def _extract_text_and_image(response):
    text = ""
    image_data = None
    candidates = getattr(response, "candidates", None) or []
    if not candidates or not getattr(candidates[0], "content", None):
        return text, image_data

    for part in getattr(candidates[0].content, "parts", None) or []:
        if getattr(part, "text", None):
            text += part.text
        inline_data = getattr(part, "inline_data", None)
        if inline_data and inline_data.data:
            encoded = base64.b64encode(inline_data.data).decode("utf-8")
            image_data = f"data:{inline_data.mime_type or 'image/jpeg'};base64,{encoded}"
    return text, image_data


def _extract_function_calls(response):
    function_calls = getattr(response, "function_calls", None) or []
    if function_calls:
        return list(function_calls)

    candidates = getattr(response, "candidates", None) or []
    if not candidates or not getattr(candidates[0], "content", None):
        return []
    return [
        part.function_call
        for part in getattr(candidates[0].content, "parts", None) or []
        if getattr(part, "function_call", None)
    ]


def _log_empty_response(response) -> None:
    candidates = getattr(response, "candidates", None) or []
    logger.warning(
        "engine.init.empty_response candidates=%s finish_reasons=%s prompt_feedback=%r usage_metadata=%r",
        len(candidates),
        [str(getattr(candidate, "finish_reason", None)) for candidate in candidates],
        getattr(response, "prompt_feedback", None),
        getattr(response, "usage_metadata", None),
    )


def upload_pdf_and_init(temp_path: str, filename: str, session_state: SessionState):
    """Upload an adventure PDF and create the model-backed game session."""
    logger.info("engine.init.upload.start", extra={"upload_filename": filename})
    uploaded_pdf = model_client.wait_for_file_processing(model_client.upload_file(temp_path))
    session_state.latest_pdf = uploaded_pdf
    session_state.chat_session = model_client.create_chat_session(
        system_instruction=build_system_instruction(),
        tools=[roll_dice, draw_scene_tool],
    )

    response = model_client.send_message(session_state.chat_session, build_initial_prompt(uploaded_pdf))
    dm_text = ""
    image_data = None

    while True:
        extracted_text, extracted_image = _extract_text_and_image(response)
        dm_text += extracted_text
        image_data = extracted_image or image_data
        function_calls = _extract_function_calls(response)
        if not function_calls:
            if not dm_text.strip():
                _log_empty_response(response)
            break

        tool_responses = []
        for function_call in function_calls:
            logger.info("engine.init.tool", extra={"tool_name": function_call.name})
            if function_call.name == "draw_scene":
                image_data = scene_renderer.render(function_call.args.get("visual_description", ""))
                tool_response = {"status": "Scene successfully rendered on the player's canvas."}
            else:
                dispatch_result = tool_dispatcher.dispatch(function_call)
                tool_response = dispatch_result.response
            tool_responses.append(types.Part.from_function_response(name=function_call.name, response=tool_response))

        response = model_client.send_message(session_state.chat_session, tool_responses)

    has_grounded_intro = bool(dm_text.strip())
    if not has_grounded_intro:
        logger.warning("engine.init.empty_intro")
        dm_text = FALLBACK_INTRO_TEXT
    if image_data is None:
        try:
            scene_prompt = _opening_scene_prompt(dm_text) if has_grounded_intro else FALLBACK_SCENE_PROMPT
            image_data = scene_renderer.render(scene_prompt)
        except Exception:
            logger.exception("engine.init.fallback_scene_failed")

    session_state.history = [{"type": "message", "role": "dm", "markdown": dm_text}]
    session_state.hero_image_url = image_data
    return dm_text, image_data


def _yield_completed_images(pending_jobs):
    completed_jobs = [job for job in pending_jobs if job.done()]
    for job in completed_jobs:
        pending_jobs.remove(job)
        try:
            image_data = job.result()
            if image_data:
                yield {"type": "image", "image_data": image_data}
        except Exception as error:
            logger.warning("scene.render.async_failed", extra={"error": str(error)})
            yield {"type": "tool_call", "message": ">> **System**: Scene generation failed."}


def process_action(player_text: str, session_state: SessionState):
    """Drive one player action and stream typed UI events."""
    chat_session = session_state.chat_session
    if not chat_session:
        yield {"type": "error", "error": "Engine not initialized. Please upload a PDF first."}
        return

    def _generate_events():
        try:
            logger.info("engine.action.start text_length=%s text_preview=%r", len(player_text), " ".join(player_text.split())[:240])
            current_input = player_text
            dm_text_full = ""
            message_id = 0
            pending_image_jobs = []
            stream_chunk_count = 0
            function_call_count = 0
            finish_reasons = []

            while True:
                response = model_client.send_message_stream(chat_session, current_input)
                text_length_before_request = len(dm_text_full.strip())
                function_calls = []
                for chunk in response:
                    stream_chunk_count += 1
                    for part in getattr(getattr((getattr(chunk, "candidates", None) or [None])[0], "content", None), "parts", None) or []:
                        if getattr(part, "text", None):
                            dm_text_full += part.text
                            yield {"type": "text_chunk", "text": part.text, "message_id": message_id}

                    finish_reasons.extend(
                        str(candidate.finish_reason)
                        for candidate in getattr(chunk, "candidates", None) or []
                        if getattr(candidate, "finish_reason", None) is not None
                    )
                    chunk_function_calls = _extract_function_calls(chunk)
                    function_calls.extend(chunk_function_calls)
                    function_call_count += len(chunk_function_calls)
                    yield from _yield_completed_images(pending_image_jobs)

                if not function_calls:
                    break

                tool_responses = []
                emitted_tool_call = False
                for function_call in function_calls:
                    dispatch_result = tool_dispatcher.dispatch(function_call)
                    for event in dispatch_result.events:
                        yield event
                        emitted_tool_call = emitted_tool_call or event["type"] == "tool_call"
                    if dispatch_result.scene_future:
                        pending_image_jobs.append(dispatch_result.scene_future)
                    tool_responses.append(
                        types.Part.from_function_response(name=function_call.name, response=dispatch_result.response)
                    )

                if (
                    len(dm_text_full.strip()) > text_length_before_request
                    and _tool_calls_only_finish_visible_turn(function_calls)
                ):
                    logger.info(
                        "engine.action.finish_after_visible_tool_calls tool_names=%s",
                        [function_call.name for function_call in function_calls],
                    )
                    break

                current_input = tool_responses
                if emitted_tool_call:
                    message_id += 1

            while pending_image_jobs:
                image_job = pending_image_jobs.pop(0)
                try:
                    image_data = image_job.result()
                    if image_data:
                        yield {"type": "image", "image_data": image_data}
                except Exception as error:
                    logger.warning("scene.render.finalize_failed", extra={"error": str(error)})
                    yield {"type": "tool_call", "message": ">> **System**: Scene generation failed."}

            if not dm_text_full and function_call_count == 0:
                logger.warning("engine.action.empty_response chunks=%s finish_reasons=%s", stream_chunk_count, finish_reasons)
                recovery_response = model_client.send_message(
                    chat_session,
                    "Continue the tabletop-RPG conversation now. The player just said "
                    f"{player_text!r}. Give a concrete, short Dungeon Master response based on the "
                    "adventure context. Do not mention this recovery instruction and do not call tools.",
                )
                recovery_text, _ = _extract_text_and_image(recovery_response)
                if recovery_text:
                    dm_text_full = recovery_text
                    yield {"type": "text_chunk", "text": recovery_text, "message_id": message_id}
                else:
                    logger.warning("engine.action.recovery_empty")

            yield {"type": "done"}
        except Exception as error:
            logger.exception("engine.action.failed", extra={"error": str(error)})
            if is_gemini_usage_limit_error(error):
                yield {
                    "type": "error",
                    "code": "usage_limit_reached",
                    "error": PUBLIC_USAGE_LIMIT_MESSAGE,
                }
            else:
                yield {"type": "error", "error": "Action processing failed."}

    turn_blocks = []
    dm_blocks_by_id = {}

    def _sync_history():
        blocks = list(turn_blocks)
        for msg_id in sorted(dm_blocks_by_id.keys()):
            if dm_blocks_by_id[msg_id]:
                blocks.append({"type": "message", "role": "dm", "markdown": dm_blocks_by_id[msg_id]})
        session_state.history = blocks

    for item in _generate_events():
        item_type = item.get("type")
        if item_type == "image":
            session_state.hero_image_url = item.get("image_data")
        elif item_type == "tool_call":
            turn_blocks.append({"type": "system", "markdown": item.get("message", "")})
            _sync_history()
        elif item_type == "text_chunk":
            msg_id = item.get("message_id", 0)
            dm_blocks_by_id[msg_id] = dm_blocks_by_id.get(msg_id, "") + item.get("text", "")
            _sync_history()
        yield item

