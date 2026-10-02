"""Small deterministic checks for the bonus orange-ball visual fallback."""

import cv2
import numpy as np

from task4 import _orange_ball_from_pixels


def test_orange_round_region_is_grounded_as_sports_ball():
    frame = np.zeros((160, 240, 3), dtype=np.uint8)
    cv2.circle(frame, (120, 80), 25, (255, 130, 0), -1)

    target = _orange_ball_from_pixels(frame)

    assert target is not None
    assert target.matches("sports ball", "orange")
    assert target.source == "color_shape"
    assert 110 <= target.center_x <= 130


def test_non_orange_regions_do_not_become_ball():
    frame = np.zeros((160, 240, 3), dtype=np.uint8)
    cv2.rectangle(frame, (20, 20), (80, 100), (0, 255, 0), -1)
    cv2.circle(frame, (160, 80), 25, (255, 0, 0), -1)

    assert _orange_ball_from_pixels(frame) is None
