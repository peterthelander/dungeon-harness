from dataclasses import dataclass, field
from typing import Any

from app.suggestions import normalize_suggestions
from app.tools import roll_dice


def draw_scene_tool(visual_description: str) -> dict:
    """Request a visual of the current scene for the player canvas."""
    return {"status": "Scene rendering request accepted."}


draw_scene_tool.__name__ = "draw_scene"


def suggest_actions_tool(suggestions: list[str]) -> dict:
    """Offer action phrases for the player UI."""
    return {"status": "Action suggestions accepted."}


suggest_actions_tool.__name__ = "suggest_actions"


@dataclass
class ToolDispatchResult:
    response: dict[str, Any]
    events: list[dict] = field(default_factory=list)
    suggestions: list[str] | None = None
    scene_future: Any = None


class ToolDispatcher:
    """Executes model tool calls and reports UI effects to the engine."""

    def __init__(self, scene_renderer):
        self._scene_renderer = scene_renderer

    def dispatch(self, function_call) -> ToolDispatchResult:
        if function_call.name == "roll_dice":
            result = roll_dice(**function_call.args)
            ui_message = result.pop("ui_message", ">> **System**: Rolling dice...")
            return ToolDispatchResult(result, events=[{"type": "tool_call", "message": ui_message}])

        if function_call.name == "draw_scene":
            future = self._scene_renderer.submit(function_call.args.get("visual_description", ""))
            if future:
                return ToolDispatchResult(
                    {"status": "Scene generation started asynchronously and will be displayed when ready."},
                    scene_future=future,
                )
            return ToolDispatchResult({"status": "Scene generation skipped because the renderer is busy."})

        if function_call.name == "suggest_actions":
            suggestions = normalize_suggestions(function_call.args.get("suggestions"))
            return ToolDispatchResult(
                {"status": "Action suggestions displayed to the player."},
                suggestions=suggestions,
            )

        return ToolDispatchResult(
            {"error": f"Tool {function_call.name} not implemented."},
            events=[{"type": "tool_call", "message": f">> **System**: Called unexpected tool `{function_call.name}`"}],
        )
