import base64
import concurrent.futures
import logging
import threading


logger = logging.getLogger(__name__)


class SceneRenderer:
    """Renders scene images without sharing results through session state."""

    def __init__(self, model_client, max_concurrent_renders: int = 4):
        self._model_client = model_client
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_renders)
        self._slots = threading.BoundedSemaphore(value=max_concurrent_renders)

    def render(self, visual_description: str) -> str | None:
        logger.info("scene.render.start")
        image_result = self._model_client.generate_image(visual_description)
        if image_result.candidates and image_result.candidates[0].content and image_result.candidates[0].content.parts:
            for part in image_result.candidates[0].content.parts:
                if part.inline_data:
                    raw_bytes = part.inline_data.data
                    b64_img = base64.b64encode(raw_bytes).decode("utf-8")
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    logger.info("scene.render.complete")
                    return f"data:{mime_type};base64,{b64_img}"
        logger.info("scene.render.complete")
        return None

    def submit(self, visual_description: str):
        if not self._slots.acquire(blocking=False):
            return None
        return self._executor.submit(self._render_with_slot, visual_description)

    def _render_with_slot(self, visual_description: str) -> str | None:
        try:
            return self.render(visual_description)
        finally:
            self._slots.release()
