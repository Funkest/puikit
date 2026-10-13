"""Modifiers on mouse events, the side buttons, and the drop operation.

Every backend that can see the keyboard reports it with each mouse event, so
an app can tell a Cmd-click, a Shift-click and a plain click apart. The side
buttons arrive as ``"back"`` / ``"forward"`` clicks. A FILE_DROP says which
operation the held keys asked for, by each platform's own rules.
"""

import sys

import pytest

from puikit.backends import _drop_policy as policy
from puikit.backends._vt_input import _sgr_mouse_records
from puikit.event import EventType


# --- the drop rules (pure, every platform) -----------------------------------

@pytest.mark.parametrize("mods, op", [
    (frozenset(), None),
    (frozenset({"cmd"}), "move"),
    (frozenset({"alt"}), "copy"),
    (frozenset({"cmd", "alt"}), "link"),
    (frozenset({"shift"}), None),
])
def test_finder_drag_modifiers(mods, op):
    assert policy.drop_operation_macos(mods) == op


@pytest.mark.parametrize("state, op", [
    (0, None),
    (policy.MK_SHIFT, "move"),
    (policy.MK_CONTROL, "copy"),
    (policy.MK_SHIFT | policy.MK_CONTROL, "link"),
    (policy.MK_ALT, "link"),
])
def test_explorer_drag_modifiers(state, op):
    assert policy.drop_operation_windows(state) == op


def test_windows_drop_modifiers():
    assert policy.drop_modifiers_windows(policy.MK_SHIFT | policy.MK_ALT) == \
        frozenset({"shift", "alt"})


# --- the terminal: SGR side buttons ------------------------------------------

def test_sgr_side_buttons_are_clicks_on_press():
    (rec,) = _sgr_mouse_records("[<128;5;3M")
    assert (rec["action"], rec["button"], rec["x"], rec["y"]) == ("click", "back", 4, 2)
    (rec,) = _sgr_mouse_records("[<145;1;1M")   # 128 + ctrl(16) + 1
    assert rec["button"] == "forward" and rec["mods"] == frozenset({"ctrl"})
    assert _sgr_mouse_records("[<128;5;3m") == [], "the release is dropped"


def test_sgr_modifiers_still_ride_left_clicks():
    (rec,) = _sgr_mouse_records("[<4;2;2M")   # shift + left
    assert rec["button"] == "left" and rec["mods"] == frozenset({"shift"})


def test_vt_backend_turns_a_side_button_into_a_click():
    from puikit.backends.vt_backend import VTBackend
    backend = VTBackend.__new__(VTBackend)
    (event,) = backend._mouse_events({"type": "mouse", "action": "click", "x": 1,
                                      "y": 2, "button": "back",
                                      "mods": frozenset({"alt"})})
    assert event.type is EventType.MOUSE_CLICK
    assert event.button == "back" and event.modifiers == frozenset({"alt"})


# --- macOS: the view's mouse handlers -----------------------------------------

macos = pytest.mark.skipif(sys.platform != "darwin", reason="AppKit")


def _view():
    from Foundation import NSMakeRect

    from puikit.backends.macos_backend import _PuiKitView

    class Backend:
        base_size = (1.0, 1.0)

    view = _PuiKitView.alloc().initWithFrame_(NSMakeRect(0, 0, 100, 100))
    view.backend = Backend()
    seen = []
    view._pk_dispatch = seen.append
    return view, seen


def _ns_mouse(kind, flags=0):
    from AppKit import NSEvent
    from Foundation import NSMakePoint
    return NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
        kind, NSMakePoint(10, 20), flags, 0, 0, None, 0, 1, 1.0)


@macos
def test_macos_left_press_and_release_carry_modifiers():
    from AppKit import (NSEventModifierFlagCommand, NSEventModifierFlagShift,
                        NSEventTypeLeftMouseDown, NSEventTypeLeftMouseUp)
    view, seen = _view()
    view.mouseDown_(_ns_mouse(NSEventTypeLeftMouseDown, NSEventModifierFlagCommand))
    view.mouseUp_(_ns_mouse(NSEventTypeLeftMouseUp, NSEventModifierFlagShift))
    assert [(e.type, e.button, e.modifiers) for e in seen] == [
        (EventType.MOUSE_DOWN, "left", frozenset({"cmd"})),
        (EventType.MOUSE_UP, "left", frozenset({"shift"})),
    ]


@macos
def test_macos_control_click_is_the_secondary_click():
    from AppKit import (NSEventModifierFlagControl, NSEventTypeLeftMouseDown,
                        NSEventTypeLeftMouseUp)
    view, seen = _view()
    view.mouseDown_(_ns_mouse(NSEventTypeLeftMouseDown, NSEventModifierFlagControl))
    view.mouseUp_(_ns_mouse(NSEventTypeLeftMouseUp, NSEventModifierFlagControl))
    assert [(e.type, e.button) for e in seen] == [(EventType.MOUSE_CLICK, "right")]


@macos
def test_macos_side_and_middle_buttons():
    from unittest.mock import MagicMock
    view, seen = _view()

    def other(number):
        event = MagicMock()
        event.buttonNumber.return_value = number
        event.modifierFlags.return_value = 0
        event.locationInWindow.return_value = (0, 0)
        return event

    view.convertPoint_fromView_ = lambda p, v: type("P", (), {"x": 1.0, "y": 2.0})()
    view.otherMouseDown_(other(3))
    view.otherMouseDown_(other(4))
    view.otherMouseDown_(other(2))
    view.otherMouseUp_(other(2))
    view.otherMouseUp_(other(3))   # a side button's release says nothing
    assert [(e.type, e.button) for e in seen] == [
        (EventType.MOUSE_CLICK, "back"),
        (EventType.MOUSE_CLICK, "forward"),
        (EventType.MOUSE_DOWN, "middle"),
        (EventType.MOUSE_UP, "middle"),
    ]
