import random
from typing import Optional

def roll_dice(
    dice_type: int,
    modifier: int = 0,
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
    if not isinstance(dice_type, int) or not 2 <= dice_type <= 1000:
        raise ValueError("dice_type must be an integer between 2 and 1000")
    if not isinstance(roll_count, int) or not 1 <= roll_count <= 100:
        raise ValueError("roll_count must be an integer between 1 and 100")
    if not isinstance(modifier, int) or abs(modifier) > 1000:
        raise ValueError("modifier must be an integer between -1000 and 1000")
    if target_dc is not None and (not isinstance(target_dc, int) or abs(target_dc) > 10000):
        raise ValueError("target_dc must be an integer between -10000 and 10000")

    rolls = [random.randint(1, dice_type) for _ in range(roll_count)]
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
