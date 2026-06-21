import pytest

from app.tools import roll_dice


def test_roll_dice_returns_expected_shape():
    result = roll_dice(dice_type=20, modifier=2, purpose="Perception", target_dc=3)

    assert 1 <= result["roll"] <= 20
    assert result["total"] == result["roll"] + 2
    assert result["success"] is True
    assert result["roll_count"] == 1


@pytest.mark.parametrize("kwargs", [
    {"dice_type": 1},
    {"dice_type": 1001},
    {"dice_type": 20, "roll_count": 0},
    {"dice_type": 20, "roll_count": 101},
])
def test_roll_dice_rejects_invalid_bounds(kwargs):
    with pytest.raises(ValueError):
        roll_dice(**kwargs)
