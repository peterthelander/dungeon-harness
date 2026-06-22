import unittest

from app.prompts import build_initial_prompt, build_system_instruction


class PromptTests(unittest.TestCase):
    def test_initial_prompt_requests_text_only_module_grounded_opening(self):
        prompt = build_initial_prompt("module.pdf")[1]

        self.assertIn("do not call dice or scene-rendering tools", prompt)
        self.assertIn("distinctive location, threat, or hook", prompt)
        self.assertIn("readiness responses only", prompt)

    def test_system_prompt_exempts_opening_greeting_from_scene_tool(self):
        instruction = build_system_instruction()

        self.assertIn("do not call 'draw_scene' during the first onboarding greeting", instruction)
        self.assertIn("suggest_actions", instruction)
        self.assertIn("never begin the adventure early", instruction)
        self.assertIn("say 'Confirm' rather than 'Confirm character'", instruction)


if __name__ == "__main__":
    unittest.main()
