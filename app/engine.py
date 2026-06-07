import base64
import time
import concurrent.futures
import google.genai as genai
from google.genai import types

from app.tools import roll_dice

# Initialize the Gemini Client natively pulling from GEMINI_API_KEY
client = genai.Client()

def draw_scene(visual_description: str, session_state: dict) -> dict:
    """Generate a scene image from a direct visual description prompt."""
    print("Generating scene thumbnail...")
    scene_prompt = visual_description.strip()
    
    image_result = client.models.generate_content(
        model='gemini-2.5-flash-image',
        contents=scene_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )
    )
    
    if image_result.candidates and image_result.candidates[0].content and image_result.candidates[0].content.parts:
        for part in image_result.candidates[0].content.parts:
            if part.inline_data:
                raw_bytes = part.inline_data.data
                b64_img = base64.b64encode(raw_bytes).decode('utf-8')
                mime_type = part.inline_data.mime_type or "image/jpeg"
                session_state["latest_scene_image_data"] = f"data:{mime_type};base64,{b64_img}"
                break
    return {"status": "Scene successfully rendered on the player's canvas."}

def _draw_scene_image_data(visual_description: str):
    """Generate scene image data URI for async execution."""
    scene_prompt = visual_description.strip()

    image_result = client.models.generate_content(
        model='gemini-2.5-flash-image',
        contents=scene_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )
    )

    if image_result.candidates and image_result.candidates[0].content and image_result.candidates[0].content.parts:
        for part in image_result.candidates[0].content.parts:
            if part.inline_data:
                raw_bytes = part.inline_data.data
                b64_img = base64.b64encode(raw_bytes).decode('utf-8')
                mime_type = part.inline_data.mime_type or "image/jpeg"
                return {"status": "Scene successfully rendered on the player's canvas."}, f"data:{mime_type};base64,{b64_img}"

    return {"status": "Scene generation completed but no image data was returned."}, None

def upload_pdf_and_init(temp_path: str, filename: str, session_state: dict):
    """ Uploads standard PDF to Gemini File API and configures system instructions """
    print(f"Uploading {filename} to Gemini...")
    uploaded_pdf = client.files.upload(file=temp_path)
    
    while uploaded_pdf.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        uploaded_pdf = client.files.get(name=uploaded_pdf.name)
    print()
    if uploaded_pdf.state.name == "FAILED":
        raise ValueError(f"Gemini failed to process the PDF: {uploaded_pdf.name}")

    session_state["latest_pdf"] = uploaded_pdf

    system_instruction = (
        "You are a human Dungeon Master (DM) playing a tabletop RPG with a friend. "
        "CRITICAL PERSONA OVERRIDE: You are NOT an AI assistant trying to be helpful or complete a task. You are NOT trying to save the user time. "
        "Your sole purpose is to maximize player agency, interactivity, and fun. "
        "Because this is an interactive game, the player must be involved in every step. Therefore:\n"
        "1. NEVER fast-forward time or resolve situations on the player's behalf. If they go to sleep, only describe the beginning of the rest. Do not skip to the next morning.\n"
        "2. If a new element is introduced (a sound, a creature, a new room), STOP immediately. Do not describe what happens next until the player reacts.\n"
        "3. Match the pacing of a real conversation. Short player inputs should generally receive shorter, focused responses. Save longer descriptions only for grand reveals of new locations.\n"
        "You must use the attached PDF strictly for setting, lore, and content. "
        "You must follow a strict, conversational turn-based flow for onboarding:\n"
        "1. Introduce the setting and WAIT for the player's reaction.\n"
        "2. Once they react, begin character creation. Present options or generate a character, and explicitly WAIT for their confirmation.\n"
        "3. Only after the character is confirmed, reveal starting rumors or immediate hooks to begin the adventure.\n"
        "ALWAYS end your turn by explicitly asking the player what they want to do or how they react, and then STOP. "
        "You MUST call the 'roll_dice' tool for any mechanical checks (attacks, skill checks, saving throws), "
        "as well as generating stats, HP, or random tables. Always use the 'purpose' parameter to describe what is being rolled. "
        "Only provide a 'target_dc' if the roll is an actual pass/fail check. "
        "Evaluate the results narratively based on the immediate action without time-skipping. "
        "CRITICAL: You must invoke the 'draw_scene' tool immediately at the start of a campaign to set the visual tone. "
        "You should also invoke it during character creation to show a portrait or thematic representation of the chosen class or race. "
        "Furthermore, you MUST call the 'draw_scene' tool on ALMOST EVERY OUT-OF-CHARACTER OR IN-CHARACTER TURN. "
        "Be incredibly active and liberal with the camera! If the player performs an action (e.g., ordering a beer, casting a spell, picking a lock), moves to a new location, opens a conspicuous chest, encounters a creature, or triggers a trap, you MUST call 'draw_scene' so the player's canvas matches the updated state of the story. "
        "The ONLY time you should skip calling 'draw_scene' is if you are engaged in a pure, back-and-forth verbal dialogue with an NPC or the DM in the exact same static visual setting as the previous turn. When in doubt, call the tool! "
        "The 'visual_description' parameter must be a standalone, rich, purely visual prompt capturing the present framing, physical entities, environment, lighting, and action. "
        "Never include text labels or refer to past frames."
    )

    print("Initializing Chat Session...")
    session_state["chat_session"] = client.chats.create(
        model='gemini-2.5-flash',
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[roll_dice, draw_scene],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
    )
    
    # Ground-truth DM intro message
    initial_prompt = [
        uploaded_pdf,
        "SYSTEM: A new player has joined the session. Here is the module PDF context above. "
        "First, invoke your 'draw_scene' tool to generate an epic, intriguing teaser image of the adventure's landscape or central mystery to hook the player. "
        "Then, write an exciting and immersive opening announcement welcoming the adventurer. "
        "End by asking them if they are ready to begin the adventure (doesn't have to be those exact words), and STOP."
    ]
    
    print("Sending initial prompt to Gemini...")
    current_response = session_state["chat_session"].send_message(initial_prompt)
    dm_text = ""
    image_data = None
    
    while True:
        try:
            # Safely check for text without triggering a warning on empty text parts
            if current_response.candidates and current_response.candidates[0].content.parts:
                for part in current_response.candidates[0].content.parts:
                    if getattr(part, "text", None):
                        dm_text += part.text
        except Exception as e:
            print(f"Warning: Failed to extract text during init (Exception: {e})")
            
        print(f"Init loop: received {len(current_response.function_calls) if current_response.function_calls else 0} function calls, current dm_text length: {len(dm_text)}")
        if not current_response.function_calls:
            break
            
        tool_responses = []
        for fc in current_response.function_calls:
            print(f"Engine init processing tool call: {fc.name}")
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
            
        current_response = session_state["chat_session"].send_message(tool_responses)
        
    if not dm_text.strip():
        print("Warning: Model failed to return introductory text. Using fallback.")
        dm_text = "Welcome to the adventure! I am your AI Game Master. What do you do?"
        
    return dm_text, image_data


def process_action(player_text: str, session_state: dict):
    """The core execution loop for driving a player action synchronously as a pure generator."""
    chat_session = session_state.get("chat_session")
    if not chat_session:
        yield {"type": "error", "error": "Engine not initialized. Please upload a PDF first."}
        return

    try:
        print(f"Player Action: {player_text}")
        current_input = player_text
        dm_text_full = ""
        pending_image_jobs = []
        image_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        
        while True:
            response = chat_session.send_message_stream(current_input)
            function_calls = []
            
            for chunk in response:
                try:
                    for part in chunk.candidates[0].content.parts:
                        if getattr(part, "text", None):
                            dm_text_full += part.text
                            yield {"type": "text_chunk", "text": part.text}
                except AttributeError:
                    # Fallback safely if stream structure is weird
                    pass

                if chunk.function_calls:
                    function_calls.extend(chunk.function_calls)

                completed_jobs = [job for job in pending_image_jobs if job["future"].done()]
                for job in completed_jobs:
                    pending_image_jobs.remove(job)
                    try:
                        _, image_data = job["future"].result()
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
                    ui_message = res.pop("ui_message", f">> **System**: Rolling dice...")
                    yield {"type": "tool_call", "message": ui_message}
                elif fc.name == "draw_scene":
                    visual_description = fc.args.get("visual_description", "")
                    future = image_executor.submit(_draw_scene_image_data, visual_description)
                    pending_image_jobs.append({"future": future, "visual_description": visual_description})
                    res = {"status": "Scene generation started asynchronously and will be displayed when ready."}
                else:
                    # Fallback trap: guarantee we always reply to an unexpected tool
                    res = {"error": f"Tool {fc.name} not implemented."}
                    yield {"type": "tool_call", "message": f">> **System**: Called unexpected tool `{fc.name}`"}
                    
                tool_responses.append(types.Part.from_function_response(name=fc.name, response=res))
            
            current_input = tool_responses

        for job in list(pending_image_jobs):
            try:
                _, image_data = job["future"].result()
                if image_data:
                    yield {"type": "image", "image_data": image_data}
            except Exception as e:
                yield {"type": "tool_call", "message": f">> **System**: Scene generation failed: {str(e)}"}

        yield {"type": "done"}
    except Exception as e:
        print(f"Action error: {e}")
        yield {"type": "error", "error": "Action processing failed."}
    finally:
        if 'image_executor' in locals():
            image_executor.shutdown(wait=False)
