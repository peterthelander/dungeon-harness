MAX_SUGGESTIONS = 4
MAX_SUGGESTION_LENGTH = 80


def normalize_suggestions(raw_suggestions) -> list[str]:
    """Return a small, unique set of safe-to-display action phrases."""
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


def suggestions_in_text(suggestions: list[str], text: str) -> list[str]:
    """Keep only suggestions that can be linked to visible DM text."""
    normalized_text = " ".join(text.split()).casefold()
    return [
        suggestion
        for suggestion in suggestions
        if " ".join(suggestion.split()).casefold() in normalized_text
    ]


def suggestions_by_message(suggestions: list[str], messages: dict[int, str]) -> dict[int, list[str]]:
    """Associate each suggestion with the latest visible DM message containing it."""
    grouped = {}
    for suggestion in suggestions:
        for message_id in sorted(messages, reverse=True):
            if suggestions_in_text([suggestion], messages[message_id]):
                grouped.setdefault(message_id, []).append(suggestion)
                break
    return grouped
