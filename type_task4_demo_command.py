"""Position the real demo terminal and type an English command into it."""

import argparse
import ctypes
import time
import urllib.request

import win32com.client
import win32clipboard
import win32gui
from PIL import ImageGrab


parser = argparse.ArgumentParser()
parser.add_argument("command", choices=("red", "green", "quit", "arrange"))
args = parser.parse_args()
matches = []
win32gui.EnumWindows(lambda hwnd, _: matches.append(hwnd)
                     if win32gui.IsWindowVisible(hwnd)
                     and "EE5112 Task4 Terminal" in win32gui.GetWindowText(hwnd) else None,
                     None)
if not matches:
    parser.error("live Task 4 terminal window not found")
window = matches[0]
screen_width, screen_height = ImageGrab.grab().size
browser_width = int(screen_width * 0.43)
win32gui.MoveWindow(window, browser_width, 0,
                    screen_width - browser_width, screen_height - 60, True)
keyboard = win32com.client.Dispatch("WScript.Shell")


def click(x, y):
    mouse = ctypes.windll.user32
    mouse.SetCursorPos(x, y)
    mouse.mouse_event(2, 0, 0, 0, 0)
    mouse.mouse_event(4, 0, 0, 0, 0)


if args.command == "arrange":
    browser = []
    win32gui.EnumWindows(lambda hwnd, _: browser.append(hwnd)
                         if win32gui.IsWindowVisible(hwnd)
                         and "Dog MuJoCo Live Tuning" in win32gui.GetWindowText(hwnd)
                         else None, None)
    if browser:
        win32gui.MoveWindow(browser[0], 0, 0, browser_width, screen_height - 60, True)
        click(200, 300)
        time.sleep(0.2)
        keyboard.SendKeys("^{HOME}")
        request = urllib.request.Request(
            "http://127.0.0.1:8765/api/camera",
            data=b'{"camera":"dog_rear_overhead_camera"}',
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(request, timeout=5).close()
    click(browser_width + 150, 350)
if args.command != "arrange":
    click(browser_width + 150, 350)
    command = ("/quit" if args.command == "quit" else
               f"Go to the {args.command} chair.")
    old_text = None
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            old_text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(command, win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()
    keyboard.SendKeys("^v")
    time.sleep(0.5)
    keyboard.SendKeys("{ENTER}")
    if old_text is not None:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(old_text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
    print(f"entered: {command}")
