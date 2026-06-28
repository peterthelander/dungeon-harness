import unittest

from app.prompts import build_initial_prompt, build_system_instruction


class PromptTests(unittest.TestCase):
    def test_initial_prompt_requests_text_only_module_grounded_opening(self):
        prompt = build_initial_prompt("module.pdf")[1]

        self.assertIn("do not call dice or scene-rendering tools", prompt)
        self.assertIn("distinctive location, threat, or hook", prompt)
        self.assertIn("immediate readiness choices", prompt)
        self.assertIn("do not create Markdown links or URLs", prompt)

    def test_system_prompt_exempts_opening_greeting_from_scene_tool(self):
        instruction = build_system_instruction()

        self.assertIn("do not call 'draw_scene' during the first onboarding greeting", instruction)
        self.assertIn("immediate choices clear in natural prose", instruction)
        self.assertIn("never begin the adventure early", instruction)
        self.assertIn("confirming or revising the hero", instruction)
        self.assertIn("interactive quick-action link", instruction)
        self.assertIn("entire next input", instruction)
        self.assertIn("natural, useful player responses", instruction)
        self.assertIn("visible objects, nearby characters", instruction)
        self.assertIn("Do not use bold for emphasis or decoration", instruction)
        self.assertIn("character statistics or numbers", instruction)
        self.assertIn("purely descriptive place names", instruction)
        self.assertIn("hidden information, puzzle solutions", instruction)
        self.assertNotIn("suggest_actions", instruction)


if __name__ == "__main__":
    unittest.main()
