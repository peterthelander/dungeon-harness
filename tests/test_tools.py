import unittest

from app.tools import roll_dice


class DiceToolTests(unittest.TestCase):
    def test_roll_dice_returns_expected_shape(self):
        result = roll_dice(dice_type=20, modifier=2, purpose="Perception", target_dc=3)

        self.assertGreaterEqual(result["roll"], 1)
        self.assertLessEqual(result["roll"], 20)
        self.assertEqual(result["total"], result["roll"] + 2)
        self.assertTrue(result["success"])
        self.assertEqual(result["roll_count"], 1)


    def test_roll_dice_rejects_invalid_bounds(self):
        for kwargs in [
            {"dice_type": 1},
            {"dice_type": 1001},
            {"dice_type": 20, "roll_count": 0},
            {"dice_type": 20, "roll_count": 101},
        ]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    roll_dice(**kwargs)
