"""
Interactive selection prompts with fuzzy search.
Falls back to basic numbered input() prompts when the terminal
does not support interactive mode (CI, piped stdin, dumb terminals).
"""

import os
import sys
import threading
import time


def clear_screen():
    """Clear the terminal screen."""
    if sys.stdout.isatty():
        os.system('cls' if sys.platform.startswith('win') else 'clear')


class Spinner:
    """A simple terminal spinner for long-running operations."""

    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message="Loading..."):
        self._message = message
        self._stop = threading.Event()
        self._thread = None

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = self._FRAMES[i % len(self._FRAMES)]
            sys.stdout.write(f"\r{frame} {self._message}")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)
        # Clear the spinner line
        sys.stdout.write("\r" + " " * (len(self._message) + 4) + "\r")
        sys.stdout.flush()

    def __enter__(self):
        if sys.stdout.isatty():
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        else:
            print(self._message)
        return self

    def __exit__(self, *args):
        self._stop.set()
        if self._thread:
            self._thread.join()


def _is_interactive():
    """Return True if stdin/stdout are TTYs."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _fuzzy_select(message, choices, default=None):
    """Use InquirerPy's fuzzy prompt for interactive selection."""
    from InquirerPy import inquirer

    result = inquirer.fuzzy(
        message=message,
        choices=choices,
        default=default,
        max_height="60%",
        mandatory=True,
    ).execute()
    return result


def _fallback_select(message, choices):
    """Plain numbered input() prompt for non-interactive terminals."""
    print(f"\n{message}")
    for idx, choice in enumerate(choices, 1):
        label = choice["name"] if isinstance(choice, dict) else str(choice)
        print(f"  {idx}. {label}")

    while True:
        try:
            selection = input("\nEnter number: ").strip()
            selected_idx = int(selection) - 1
            if 0 <= selected_idx < len(choices):
                c = choices[selected_idx]
                return c["value"] if isinstance(c, dict) else c
            print(f"Please enter a number between 1 and {len(choices)}")
        except ValueError:
            print("Please enter a valid number")
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled")
            sys.exit(0)


def interactive_select(message, choices, default=None):
    """
    Present a selection menu to the user.

    Parameters
    ----------
    message : str
        The prompt text shown above the list.
    choices : list[dict]
        Each dict has 'name' (display string) and 'value' (returned on selection).
    default : str, optional
        Pre-selected value.

    Returns
    -------
    The 'value' of the chosen item.
    """
    if len(choices) == 1:
        only = choices[0]
        label = only["name"] if isinstance(only, dict) else str(only)
        value = only["value"] if isinstance(only, dict) else only
        print(f"\n{message}")
        print(f"  Auto-selected: {label}")
        return value

    if _is_interactive():
        try:
            return _fuzzy_select(message, choices, default)
        except Exception:
            pass

    return _fallback_select(message, choices)
