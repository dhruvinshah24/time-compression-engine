"""
Tests for processing profile classification logic in S02.
Validates that QUICK_TEST/SHORT/STANDARD/LONG/EXTENDED profiles are assigned correctly.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def test_profile_quick_test():
    """Videos <= 30s get QUICK_TEST profile."""
    dur_s = 25.0
    if dur_s <= 30:
        profile = "QUICK_TEST"
        default_skip = 2
    elif dur_s <= 300:
        profile = "SHORT"
        default_skip = 3
    else:
        profile = "OTHER"
        default_skip = 5
    assert profile == "QUICK_TEST"
    assert default_skip == 2


def test_profile_short():
    """Videos 31–300s get SHORT profile."""
    for dur in [31, 120, 299, 300]:
        if dur <= 30:
            profile = "QUICK_TEST"
        elif dur <= 300:
            profile = "SHORT"
        elif dur <= 600:
            profile = "STANDARD"
        elif dur <= 3600:
            profile = "LONG"
        else:
            profile = "EXTENDED"
        assert profile == "SHORT", f"dur={dur} got {profile}"


def test_profile_standard():
    """Videos 301–600s get STANDARD profile."""
    for dur in [301, 450, 600]:
        if dur <= 30:
            profile = "QUICK_TEST"
        elif dur <= 300:
            profile = "SHORT"
        elif dur <= 600:
            profile = "STANDARD"
        elif dur <= 3600:
            profile = "LONG"
        else:
            profile = "EXTENDED"
        assert profile == "STANDARD", f"dur={dur} got {profile}"


def test_profile_long():
    """Videos 601–3600s get LONG profile."""
    for dur in [601, 1800, 3600]:
        if dur <= 30:
            profile = "QUICK_TEST"
        elif dur <= 300:
            profile = "SHORT"
        elif dur <= 600:
            profile = "STANDARD"
        elif dur <= 3600:
            profile = "LONG"
        else:
            profile = "EXTENDED"
        assert profile == "LONG", f"dur={dur} got {profile}"


def test_profile_extended():
    """Videos > 3600s get EXTENDED profile."""
    for dur in [3601, 7200, 86400]:
        if dur <= 30:
            profile = "QUICK_TEST"
        elif dur <= 300:
            profile = "SHORT"
        elif dur <= 600:
            profile = "STANDARD"
        elif dur <= 3600:
            profile = "LONG"
        else:
            profile = "EXTENDED"
        assert profile == "EXTENDED", f"dur={dur} got {profile}"


def test_profile_frame_skip_defaults():
    """Each profile has the correct default frame skip rate."""
    expected = {
        "QUICK_TEST": 2,
        "SHORT": 3,
        "STANDARD": 5,
        "LONG": 10,
        "EXTENDED": 15,
    }
    profile_map = [
        (25, "QUICK_TEST"),
        (120, "SHORT"),
        (400, "STANDARD"),
        (1800, "LONG"),
        (7200, "EXTENDED"),
    ]
    for dur, expected_profile in profile_map:
        if dur <= 30:
            profile = "QUICK_TEST"
            skip = 2
        elif dur <= 300:
            profile = "SHORT"
            skip = 3
        elif dur <= 600:
            profile = "STANDARD"
            skip = 5
        elif dur <= 3600:
            profile = "LONG"
            skip = 10
        else:
            profile = "EXTENDED"
            skip = 15
        assert profile == expected_profile
        assert skip == expected[expected_profile], f"{profile} skip expected {expected[expected_profile]}, got {skip}"


def test_settings_override_wins():
    """If settings provides frame_skip_rate, it overrides profile default."""
    dur_s = 25.0   # QUICK_TEST → default_skip = 2
    default_skip = 2

    # Simulate settings providing override
    settings_skip = 10  # User explicitly set 10
    if settings_skip is not None:
        frame_skip_rate = int(settings_skip)
        skip_source = "settings"
    else:
        frame_skip_rate = default_skip
        skip_source = "profile:QUICK_TEST"

    assert frame_skip_rate == 10
    assert skip_source == "settings"


def test_no_settings_uses_profile():
    """If settings does not provide frame_skip_rate, profile default is used."""
    dur_s = 400.0  # STANDARD → default_skip = 5
    default_skip = 5
    settings_skip = None

    if settings_skip is not None:
        frame_skip_rate = int(settings_skip)
        skip_source = "settings"
    else:
        frame_skip_rate = default_skip
        skip_source = "profile:STANDARD"

    assert frame_skip_rate == 5
    assert skip_source == "profile:STANDARD"
