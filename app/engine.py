import base64
import time
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
    
    if image_result.candidates and image_result.candidates[0].content.parts:
        for part in image_result.candidates[0].content.parts:
            if part.inline_data:
                raw_bytes = part.inline_data.data
                b64_img = base64.b64encode(raw_bytes).decode('utf-8')
                mime_type = part.inline_data.mime_type or "image/jpeg"
                session_state["latest_scene_image_data"] = f"data:{mime_type};base64,{b64_img}"
                break
    return {"status": "Scene successfully rendered on the player's canvas."}

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
        "You have a tool named 'draw_scene'. You must invoke 'draw_scene' ONLY when a major narrative change, a new room entry, or a combat encounter occurs. "
        "Do not call it for minor dialogue exchanges or routine rule tracking. "
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
    initial_response = session_state["chat_session"].send_message([
        "SYSTEM: A new player has joined the session. Here is the module PDF context. "
        "Please write a highly exciting and immersive opening announcement welcoming the brave adventurer to this specific adventure "
        "(hint at the lore and intrigue without spoilers). "
        "END YOUR MESSAGE by asking the player if they are ready to answer the call, and STOP. "
        "DO NOT begin character creation yet.",
        uploaded_pdf
    ])
    
    dm_text = initial_response.text
    image_data = None
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
        
        while True:
            response = chat_session.send_message_stream(current_input)
            function_calls = []
            
            for chunk in response:
                if chunk.text:
                    dm_text_full += chunk.text
                    yield {"type": "text_chunk", "text": chunk.text}
                if chunk.function_calls:
                    function_calls.extend(chunk.function_calls)
                    
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
                    res = draw_scene(visual_description=visual_description, session_state=session_state)
                    image_data = session_state.pop("latest_scene_image_data", None)
                    if image_data:
                        yield {"type": "image", "image_data": image_data}
                else:
                    # Fallback trap: guarantee we always reply to an unexpected tool
                    res = {"error": f"Tool {fc.name} not implemented."}
                    yield {"type": "tool_call", "message": f">> **System**: Called unexpected tool `{fc.name}`"}
                    
                tool_responses.append(types.Part.from_function_response(name=fc.name, response=res))
            
            current_input = tool_responses

        yield {"type": "done"}
    except Exception as e:
        print(f"Action error: {e}")
        yield {"type": "error", "error": str(e)}
