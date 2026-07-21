PUBLIC_USAGE_LIMIT_MESSAGE = (
    "The public playtest has reached its current Gemini usage limit. "
    "Thanks—the dungeon was more popular than expected! Please try again later."
)


def is_gemini_usage_limit_error(error: BaseException) -> bool:
    """Return whether an SDK exception represents Gemini quota exhaustion."""
    seen = set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        values = (
            getattr(current, "code", None),
            getattr(current, "status", None),
            getattr(current, "status_code", None),
        )
        normalized = {str(value).upper() for value in values if value is not None}
        message = str(current).upper()
        if "429" in normalized or "RESOURCE_EXHAUSTED" in normalized:
            return True
        if "RESOURCE_EXHAUSTED" in message or "429 TOO MANY REQUESTS" in message:
            return True
        current = current.__cause__ or current.__context__
    return False
