import base64
import time
import google.genai as genai
from google.genai import types

from app.state import engine_state
from app.tools import roll_dice

# Initialize the Gemini Client natively pulling from GEMINI_API_KEY
client = genai.Client()

def _generate_scene_image(dm_text: str) -> str:
    """ Helper to summarize the DM's text into a purely visual prompt and generate an image. """
    print("Extracting visual prompt from DM text...")
    
    prev_visual_desc = engine_state.get("previous_visual_desc", "")
    if prev_visual_desc:
        context_instruction = (
            "Here is the purely visual description of the PREVIOUS scene to help maintain consistency of the characters' appearances and the current environment:\n"
            f"> {prev_visual_desc}\n\n"
            "Based on the new narration below, write a new updated purely visual description. "
            "Update the scenery, character poses, or lighting only if the narration implies a change (e.g., they moved to a new room or a creature appeared). "
            "Keep the core character appearance details entirely consistent.\n\n"
        )
    else:
        context_instruction = "Based on the following narration from a tabletop RPG session, write a very concise, purely visual description of the setting and action. "

    visual_prompt_instructions = (
        f"{context_instruction}"
        "Do not include any character names, stats, dialogue, or non-visual abstract concepts. "
        "Focus ONLY on the physical environment, character designs, lighting, atmosphere, and what can be physically seen.\n\n"
        f"Narration:\n{dm_text[:1500]}"
    )
    
    visual_desc_response = client.models.generate_content(
        model='gemini-2.5-flash-lite',
        contents=visual_prompt_instructions
    )
    visual_desc = visual_desc_response.text.strip()
    
    engine_state["previous_visual_desc"] = visual_desc
    
    print("Generating scene thumbnail...")
    scene_prompt = f"A gorgeous, clean visual painting of a fantasy TTRPG landscape representing: {visual_desc}. Maintain visual continuity securely."
    
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
                return f"data:{mime_type};base64,{b64_img}"
    return None

def upload_pdf_and_init(temp_path: str, filename: str):
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

    engine_state["latest_pdf"] = uploaded_pdf

    system_instruction = (
        "You are the DM (Dungeon Master) of a minimalist tabletop RPG engine. "
        "You must use the attached PDF strictly for setting, lore, and content. "
        "CRITICAL PACING: Do not rush! NEVER dump exposition, character creation, and rumors all in one message. "
        "You must follow a strict, conversational turn-based flow:\n"
        "1. Introduce the setting and WAIT for the player's reaction.\n"
        "2. Once they react, begin character creation. Present options or generate a character, and explicitly WAIT for their confirmation.\n"
        "3. Only after the character is confirmed, reveal starting rumors or immediate hooks to begin the adventure.\n"
        "ALWAYS end your turn by asking the player what they want to do or how they react, and then STOP. "
        "You MUST call the 'roll_dice' tool for any mechanical checks (attacks, skill checks, saving throws), "
        "as well as generating stats, HP, or random tables. Always use the 'purpose' parameter to describe what is being rolled. "
        "Only provide a 'target_dc' if the roll is an actual pass/fail check. "
        "Evaluate the results narratively. Keep your responses engaging, descriptive, but reasonably concise."
    )

    print("Initializing Chat Session...")
    engine_state["chat_session"] = client.chats.create(
        model='gemini-2.5-flash',
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[roll_dice],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
    )
    
    # Ground-truth DM intro message
    initial_response = engine_state["chat_session"].send_message([
        "SYSTEM: A new player has joined the session. Here is the module PDF context. "
        "Please write a highly exciting and immersive opening announcement welcoming the brave adventurer to this specific adventure "
        "(hint at the lore and intrigue without spoilers). "
        "END YOUR MESSAGE by asking the player if they are ready to answer the call, and STOP. "
        "DO NOT begin character creation yet.",
        uploaded_pdf
    ])
    
    dm_text = initial_response.text
    image_data = None
    try:
        image_data = _generate_scene_image(dm_text)
    except Exception as img_err:
        print(f"Initial thumbnail generation skipped/failed: {img_err}")
        
    return dm_text, image_data


def process_action(player_text: str):
    """The core execution loop for driving a player action synchronously as a pure generator."""
    chat_session = engine_state.get("chat_session")
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
                else:
                    # Fallback trap: guarantee we always reply to an unexpected tool
                    res = {"error": f"Tool {fc.name} not implemented."}
                    yield {"type": "tool_call", "message": f">> **System**: Called unexpected tool `{fc.name}`"}
                    
                tool_responses.append(types.Part.from_function_response(name=fc.name, response=res))
            
            current_input = tool_responses

        yield {"type": "status", "message": "Synthesizing scene visuals..."}

        if dm_text_full.strip():
            try:
                image_data = _generate_scene_image(dm_text_full)
                if image_data:
                    yield {"type": "image", "image_data": image_data}
            except Exception as img_err:
                print(f"Thumbnail generation skipped/failed: {img_err}")

        yield {"type": "done"}
    except Exception as e:
        print(f"Action error: {e}")
        yield {"type": "error", "error": str(e)}
