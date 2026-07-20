import logging

from flask import jsonify


logger = logging.getLogger(__name__)

WELCOME_IMAGE_PROMPT = """
Create cinematic dark-fantasy key art for the welcome screen of a solo roleplaying game.
A solitary, anonymous cloaked adventurer stands at the threshold of a colossal ancient
stone doorway, seen from behind, looking into a mysterious impossible world with a
distant ruined spire and a faint winding path. Use warm lantern amber against cool
moonlit charcoal and deep-blue mist, with restrained crimson accents. Compose this as
a wide landscape with the doorway and adventurer right of center and generous dark,
quiet negative space on the left for interface copy. It must crop gracefully on a
portrait phone screen. Sophisticated painterly fantasy concept art; atmospheric,
grounded, inviting, and dangerous. No typography, letters, logos, UI, watermark,
recognizable franchise imagery, dragons, combat, or visible face.
""".strip()


def register_welcome_image_route(app):
    @app.route("/welcome-image", methods=["GET"])
    def welcome_image():
        try:
            # Import lazily so the regular app and route tests do not initialize an
            # image model until this optional artwork is actually requested.
            from app.engine import scene_renderer

            image_data = scene_renderer.render(WELCOME_IMAGE_PROMPT)
            if not image_data:
                return jsonify({"image_data": None}), 503
            return jsonify({"image_data": image_data})
        except Exception:
            logger.exception("welcome_image.failed")
            return jsonify({"image_data": None}), 503
