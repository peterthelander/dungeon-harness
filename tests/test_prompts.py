import unittest

from app.prompts import build_initial_prompt, build_system_instruction


class PromptTests(unittest.TestCase):
    def test_initial_prompt_requests_text_only_module_grounded_opening(self):
        prompt = build_initial_prompt("module.pdf")[1]

        self.assertIn("do not call any tools", prompt)
        self.assertIn("distinctive location, threat, or hook", prompt)

    def test_system_prompt_exempts_opening_greeting_from_scene_tool(self):
        instruction = build_system_instruction()

        self.assertIn("do not call 'draw_scene' during the first onboarding greeting", instruction)


if __name__ == "__main__":
    unittest.main()
