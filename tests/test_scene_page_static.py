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

    def test_uninitialized_session_uses_chat_lobby(self):
        index = read_static_file("index.html")
        script = read_static_file("script.js")

        self.assertNotIn('class="preset-modules"', index)
        self.assertIn('id="pdf-upload"', index)
        self.assertIn("const PRESET_MODULES", script)
        self.assertIn("function buildModuleLobbyText", script)
        self.assertIn("appendMessage(buildModuleLobbyText(), 'dm')", script)
        self.assertIn("document.getElementById('dashboard').style.display = 'flex';", script)

    def test_preset_module_inline_action_loads_url(self):
        script = read_static_file("script.js")

        self.assertIn("function findPresetModule", script)
        self.assertIn("loadPresetModuleFromChat(presetModule)", script)
        self.assertIn("appendMessage(presetModule.label, 'player')", script)
        self.assertIn("await loadUrl(presetModule.url)", script)

    def test_scene_page_renderer_uses_page_data_model(self):
        script = read_static_file("script.js")

        self.assertIn("@typedef {Object} ScenePageData", script)
        self.assertIn("heroImageUrl", script)
        self.assertIn("narrative", script)
        self.assertNotIn("suggestedActions", script)
        self.assertNotIn("linkifySuggestions", script)
        self.assertIn("function activateBoldActions", script)
        self.assertIn("function isActionableBoldLabel", script)
        self.assertIn("querySelectorAll('strong')", script)
        self.assertIn("sendAction(label)", script)
        self.assertIn("const ScenePage", script)

    def test_new_action_keeps_current_scene_until_response_starts(self):
        script = read_static_file("script.js")

        self.assertIn("appendMessage(text, 'player');", script)
        self.assertIn("function startFreshScene()", script)
        self.assertIn("if (data.type === 'text_chunk') {\n                        startFreshScene();", script)
        self.assertNotIn("resetScenePage();\n    ScenePage.render(scenePageData, { stickToTop: true });\n    ScenePage.clearInput();", script)

    def test_bold_actions_skip_stat_labels(self):
        script = read_static_file("script.js")

        self.assertIn("^[A-Za-z][A-Za-z ]+:", script)
        self.assertIn("isActionableBoldLabel(label)", script)
        self.assertNotIn("QUESTION_FRAGMENT_PATTERNS", script)
        self.assertNotIn("pattern.test(label)", script)

    def test_upload_pdf_inline_action_uses_file_picker(self):
        script = read_static_file("script.js")

        self.assertIn("function handleInlineAction", script)
        self.assertIn("normalizedLabel === 'upload a pdf'", script)
        self.assertIn("function triggerUploadFromChat", script)
        self.assertIn("fileInput.click()", script)
        self.assertIn("initializeEngine({ fromChat: true })", script)
        self.assertIn("setupPdfUploadInput();", script)

    def test_restart_inline_action_calls_restart_endpoint(self):
        script = read_static_file("script.js")

        self.assertIn("normalizedLabel === 'restart this module'", script)
        self.assertIn("function restartCurrentModule", script)
        self.assertIn("fetch('/restart', { method: 'POST' })", script)
        self.assertIn("appendMessage('Restart this module', 'player')", script)

    def test_bold_actions_have_inline_button_styles(self):
        style = read_static_file("style.css")

        self.assertIn(".message.dm .inline-action", style)
        self.assertIn("font-weight: 700", style)
        self.assertIn(".inline-action--inactive", style)
        self.assertIn(".message.system + .message.system", style)
        self.assertIn("align-self: stretch", style)
        self.assertIn("margin-bottom: 0.35em", style)

    def test_scene_page_css_owns_responsive_layout(self):
        style = read_static_file("style.css")

        self.assertIn(".scene-page-scroll", style)
        self.assertIn(".scene-page__layout--with-hero", style)
        self.assertIn("grid-template-columns: minmax(320px, 0.85fr) minmax(380px, 1.15fr)", style)
        self.assertIn('grid-template-areas: "content hero"', style)
        self.assertIn("@media (max-width: 980px), (orientation: portrait)", style)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", style)
        self.assertIn('grid-template-areas: "hero"', style)


if __name__ == "__main__":
    unittest.main()
