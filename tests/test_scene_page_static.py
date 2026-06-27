from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read_static_file(name):
    return (ROOT / "app" / "static" / name).read_text()


class ScenePageStaticTests(unittest.TestCase):
    def test_dashboard_mounts_single_scene_page_root(self):
        index = read_static_file("index.html")

        self.assertIn('id="scene-page-root"', index)
        self.assertNotIn('id="image-canvas-container"', index)
        self.assertNotIn('id="chat-window"', index)

    def test_scene_page_renderer_uses_page_data_model(self):
        script = read_static_file("script.js")

        self.assertIn("@typedef {Object} ScenePageData", script)
        self.assertIn("heroImageUrl", script)
        self.assertIn("narrative", script)
        self.assertNotIn("suggestedActions", script)
        self.assertNotIn("linkifySuggestions", script)
        self.assertIn("const ScenePage", script)

    def test_new_action_keeps_current_scene_until_response_starts(self):
        script = read_static_file("script.js")

        self.assertIn("appendMessage(text, 'player');", script)
        self.assertIn("function startFreshScene()", script)
        self.assertIn("if (data.type === 'text_chunk') {\n                        startFreshScene();", script)
        self.assertNotIn("resetScenePage();\n    ScenePage.render(scenePageData, { stickToTop: true });\n    ScenePage.clearInput();", script)

    def test_scene_page_css_owns_responsive_layout(self):
        style = read_static_file("style.css")

        self.assertIn(".scene-page-scroll", style)
        self.assertIn(".scene-page__layout--with-hero", style)
        self.assertIn("grid-template-columns: minmax(0, 1fr) minmax(280px, 42%)", style)
        self.assertIn('grid-template-areas: "content hero"', style)
        self.assertIn("@media (max-width: 900px) and (orientation: portrait)", style)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", style)
        self.assertIn('grid-template-areas: "hero"', style)


if __name__ == "__main__":
    unittest.main()
