"""Quit requests: the platform asking the app to quit (Backend.set_quit_handler).

The macOS application menu's Quit and the Dock's, and the main window's close
button, used to end the process at once. With a handler set they go to the
app, which decides and calls quit() itself. The portable half runs anywhere;
the macOS half builds real NSMenus without opening a window.
"""

import sys

import pytest

from puikit import Panel
from puikit.backends.memory_backend import MemoryBackend


def test_no_handler_means_quit_as_before():
    backend = MemoryBackend()
    assert backend._quit_request() is False


def test_a_handler_takes_the_request():
    backend = MemoryBackend()
    asked = []
    backend.set_quit_handler(lambda: asked.append(True), shortcut="Cmd-Q")
    assert backend._quit_request() is True
    assert asked == [True]
    assert backend._quit_shortcut == "Cmd-Q"


def test_clearing_the_handler_restores_the_default():
    backend = MemoryBackend()
    backend.set_quit_handler(lambda: None)
    backend.set_quit_handler(None)
    assert backend._quit_request() is False


def test_the_panel_hands_the_handler_to_its_backend():
    backend = MemoryBackend()
    backend.open()
    panel = Panel(backend)
    asked = []
    panel.set_quit_handler(lambda: asked.append(True), shortcut="Q")
    assert backend._quit_request() is True
    assert asked == [True]
    assert backend._quit_shortcut == "Q"


# --------------------------------------------------------------------------- #
# macOS
# --------------------------------------------------------------------------- #

mac = pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only backend")


class _FakeKeyEvent:
    def __init__(self, chars, flags):
        self._chars = chars
        self._flags = flags

    def charactersIgnoringModifiers(self):
        return self._chars

    def modifierFlags(self):
        return self._flags


def _quit_item(main):
    """The application menu's first item, and that menu."""
    app_menu = main.itemAtIndex_(0).submenu()
    return app_menu.itemAtIndex_(0), app_menu


@mac
def test_without_a_handler_quit_is_the_standard_terminate_item():
    pytest.importorskip("AppKit")
    from AppKit import NSEventModifierFlagCommand
    from puikit.backends import _macos_menu as mm
    from puikit.menu import Menu

    main, _responder = mm.build_menu_bar(Menu(), "App")
    item, app_menu = _quit_item(main)
    assert not isinstance(app_menu, mm._NonFiringMenu)
    assert item.action() == "terminate:"
    assert item.keyEquivalent() == "q"
    assert item.keyEquivalentModifierMask() & NSEventModifierFlagCommand


@mac
def test_with_a_handler_quit_shows_the_apps_key_and_only_displays_it():
    pytest.importorskip("AppKit")
    from AppKit import NSEventModifierFlagCommand
    from puikit.backends import _macos_menu as mm
    from puikit.menu import Menu

    main, _responder = mm.build_menu_bar(Menu(), "App", quit=(lambda: None, "Cmd-Q"))
    item, app_menu = _quit_item(main)
    assert isinstance(app_menu, mm._NonFiringMenu)      # never fires by key
    assert item.action() != "terminate:"
    assert item.keyEquivalent() == "q"
    assert item.keyEquivalentModifierMask() & NSEventModifierFlagCommand

    main, _responder = mm.build_menu_bar(Menu(), "App", quit=(lambda: None, "Q"))
    item, _menu = _quit_item(main)
    assert (item.keyEquivalent(), item.keyEquivalentModifierMask()) == ("q", 0)

    main, _responder = mm.build_menu_bar(Menu(), "App", quit=(lambda: None, None))
    item, _menu = _quit_item(main)
    assert item.keyEquivalent() == ""


@mac
def test_choosing_quit_calls_the_handler_even_under_a_modal_layer(monkeypatch):
    pytest.importorskip("AppKit")
    from puikit.backends import _macos_menu as mm
    from puikit.menu import Menu

    asked = []
    main, responder = mm.build_menu_bar(
        Menu(), "App", forward_key=lambda ev: None, is_active=lambda: False,
        quit=(lambda: asked.append(True), "Cmd-Q"))
    item, _menu = _quit_item(main)
    monkeypatch.setattr(mm, "_current_key_event", lambda: None)   # a mouse choice
    responder._quit_responder.fire_(item)
    assert asked == [True]
    assert responder._quit_responder.validateMenuItem_(item) is True


@mac
def test_the_quit_chord_goes_to_the_apps_keymap(monkeypatch):
    pytest.importorskip("AppKit")
    from AppKit import NSEventModifierFlagCommand
    from puikit.backends import _macos_menu as mm
    from puikit.menu import Menu

    asked, forwarded = [], []
    main, responder = mm.build_menu_bar(
        Menu(), "App", forward_key=forwarded.append,
        quit=(lambda: asked.append(True), "Cmd-Q"))
    item, _menu = _quit_item(main)
    chord = _FakeKeyEvent("q", NSEventModifierFlagCommand)
    monkeypatch.setattr(mm, "_current_key_event", lambda: chord)
    responder._quit_responder.fire_(item)
    assert forwarded == [chord] and asked == []


@mac
def test_terminate_and_the_close_button_go_to_the_handler():
    pytest.importorskip("AppKit")
    from AppKit import NSTerminateCancel, NSTerminateNow
    from puikit.backends.macos_backend import (MacOSBackend, _PuiKitAppDelegate,
                                               _PuiKitWindowDelegate)

    backend = MacOSBackend.__new__(MacOSBackend)
    backend._main_window_close = "quit"
    app_delegate = _PuiKitAppDelegate.alloc().init()
    app_delegate.backend = backend
    window_delegate = _PuiKitWindowDelegate.alloc().init()
    window_delegate.backend = backend

    assert app_delegate.applicationShouldTerminate_(None) == NSTerminateNow
    assert window_delegate.windowShouldClose_(None) is True

    asked = []
    backend._quit_handler = lambda: asked.append(True)
    assert app_delegate.applicationShouldTerminate_(None) == NSTerminateCancel
    assert window_delegate.windowShouldClose_(None) is False
    assert asked == [True, True]
