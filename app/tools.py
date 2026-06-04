import random
from typing import Optional

def roll_dice(
    dice_type: int,
    modifier: int,
    purpose: str = "general",
    target_dc: Optional[int] = None,
    roll_count: int = 1
) -> dict:
    """
    Simulates a dice roll mechanic in a tabletop game.
    
    Args:
        dice_type: The number of sides on each die (e.g., 20 for a d20).
        modifier: The static bonus or penalty applied to the roll.
        purpose: A short description of what this roll is for (e.g., 'STR stat generation', 'Perception check').
        target_dc: The target Difficulty Class to meet or exceed for success. Omit this if the roll is not a pass/fail check (like rolling stats or tables).
        roll_count: Number of dice to roll (e.g., 3 for 3d6).
    
    Returns:
        dict: The result of the roll, the final total, and whether it was a success (if applicable).
    """
    rolls = [random.randint(1, dice_type) for _ in range(max(1, roll_count))]
    base_total = sum(rolls)
    total = base_total + modifier
    
    operator = "+" if modifier >= 0 else ""
    msg = f"🎲 **Rolling {len(rolls)}d{dice_type} {operator}{modifier}**"
    
    if purpose and purpose.lower() != "general":
        msg += f" (for *{purpose}*)"
    
    roll_details = " + ".join(str(r) for r in rolls)
    msg += f"...\n> Rolls: {roll_details}\n> Result: **{total}**"
    
    result = {
        "roll": base_total,
        "rolls": rolls,
        "roll_count": len(rolls),
        "modifier": modifier,
        "total": total,
        "purpose": purpose
    }
    
    if target_dc is not None:
        success = total >= target_dc
        msg += f" {'(Success!)' if success else '(Failure)'} [DC: {target_dc}]"
        result["target_dc"] = target_dc
        result["success"] = success
         
    result["ui_message"] = msg
    return result
