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
        self.assertIn("suggestedActions", script)
        self.assertIn("const ScenePage", script)

    def test_new_action_starts_a_fresh_scene_page(self):
        script = read_static_file("script.js")

        self.assertIn("function resetScenePage()", script)
        self.assertIn("resetScenePage();\n    ScenePage.render(scenePageData, { stickToTop: true });\n    ScenePage.clearInput();", script)
        self.assertNotIn("appendMessage(text, 'player')", script)

    def test_scene_page_css_owns_responsive_layout(self):
        style = read_static_file("style.css")

        self.assertIn(".scene-page-scroll", style)
        self.assertIn(".scene-page__layout--with-hero", style)
        self.assertIn("grid-template-columns: minmax(280px, 42%) minmax(0, 1fr)", style)
        self.assertIn("@media (max-width: 900px) and (orientation: portrait)", style)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", style)


if __name__ == "__main__":
    unittest.main()
