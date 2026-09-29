"""Position the real demo terminal and type an English command into it."""

import argparse
import time

import win32com.client
import win32gui


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
win32gui.MoveWindow(window, 1560, 0, 2280, 2100, True)
if args.command != "arrange":
    keyboard = win32com.client.Dispatch("WScript.Shell")
    if not keyboard.AppActivate("EE5112 Task4 Terminal"):
        parser.error("could not focus Task 4 terminal")
    command = ("/quit" if args.command == "quit" else
               f"Go to the {args.command} chair.")
    for char in command:
        keyboard.SendKeys(char)
        time.sleep(0.09)
    keyboard.SendKeys("{ENTER}")
    print(f"typed: {command}")
