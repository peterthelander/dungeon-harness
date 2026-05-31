import random
from typing import Optional
from app.state import get_active_queue

def roll_dice(dice_type: int, modifier: int, purpose: str = "general", target_dc: Optional[int] = None) -> dict:
    """
    Simulates a dice roll mechanic in a tabletop game.
    
    Args:
        dice_type: The number of sides on the dice (e.g., 20 for a d20).
        modifier: The static bonus or penalty applied to the roll.
        purpose: A short description of what this roll is for (e.g., 'STR stat generation', 'Perception check').
        target_dc: The target Difficulty Class to meet or exceed for success. Omit this if the roll is not a pass/fail check (like rolling stats or tables).
    
    Returns:
        dict: The result of the roll, the final total, and whether it was a success (if applicable).
    """
    roll = random.randint(1, dice_type)
    total = roll + modifier
    
    # Send a side-effect tool notification to the frontend
    q = get_active_queue()
    if q:
        operator = "+" if modifier >= 0 else ""
        msg = f"🎲 **Rolling d{dice_type} {operator}{modifier}**"
        
        if purpose and purpose.lower() != "general":
            msg += f" (for *{purpose}*)"
            
        msg += f"...\n> Result: **{total}**"
        
        if target_dc is not None:
             success = total >= target_dc
             msg += f" {'(Success!)' if success else '(Failure)'} [DC: {target_dc}]"
             
        q.put({"type": "tool_call", "message": msg})
    
    # We return the dictionary which the model will parse natively to describe the outcome.
    result = {
        "roll": roll,
        "modifier": modifier,
        "total": total,
        "purpose": purpose
    }
    
    if target_dc is not None:
        result["target_dc"] = target_dc
        result["success"] = total >= target_dc
        
    return result