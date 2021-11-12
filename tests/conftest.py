import time
import tkinter
import sys
import subprocess
from pathlib import Path

from irc_client import gui

import pytest


@pytest.fixture(scope="session")
def root_window():
    root = tkinter.Tk()
    yield root
    root.destroy()


@pytest.fixture
def wait_until(root_window):
    def actually_wait_until(condition, *, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            root_window.update()
            if condition():
                return
        raise RuntimeError("timed out waiting")

    return actually_wait_until


class _Hircd:
    def __init__(self, hircd_repo):
        self._hircd_repo = hircd_repo
        self.process = None

    def start(self):
        self.process = subprocess.Popen(
            [sys.executable, "hircd.py", "--foreground", "--verbose", "--log-stdout"],
            stderr=subprocess.PIPE,
            cwd=self._hircd_repo,
        )

        # Wait for it to start
        for line in self.process.stderr:
            assert b"ERROR" not in line
            if line.startswith(b"[INFO] Starting hircd on "):
                port = int(line.split(b":")[-1])
                return port
        raise RuntimeError

    def stop(self):
        self.process.kill()

        output = self.process.stderr.read()
        if b"ERROR" in output:
            print(output.decode("utf-8", errors="replace"))
            raise RuntimeError


@pytest.fixture
def hircd():
    hircd_repo = Path(__file__).absolute().parent / "hircd"
    if not hircd_repo.is_dir():
        subprocess.check_call(
            ["git", "clone", "https://github.com/Akuli/hircd"], cwd=hircd_repo.parent
        )

    correct_commit = "d1ab8a40e0921626fef276431ee0dcd4d3e53403"  # on py3 branch
    actual_commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=hircd_repo)
        .strip()
        .decode("ascii")
    )
    if actual_commit != correct_commit:
        subprocess.check_call(["git", "fetch"], cwd=hircd_repo)
        subprocess.check_call(["git", "checkout", correct_commit], cwd=hircd_repo)

    hircd = _Hircd(hircd_repo)
    hircd.start()
    yield hircd
    hircd.stop()


@pytest.fixture
def alice_and_bob(hircd, root_window, wait_until):
    widgets = {}
    for name in ["Alice", "Bob"]:
        widgets[name] = gui.IrcWidget(
            root_window,
            {
                "host": "localhost",
                "port": 6667,
                "ssl": False,
                "nick": name,
                "username": name,
                "realname": f"{name}'s real name",
                "joined_channels": ["#autojoin"],
            },
        )
        widgets[name].pack(fill="both", expand=True)
        widgets[name].handle_events()
        wait_until(lambda: widgets[name].find_channel("#autojoin"))

    yield widgets

    for widget in widgets.values():
        widget.core.quit()
        widget.core.wait_until_stopped()


@pytest.fixture
def alice(alice_and_bob):
    return alice_and_bob["Alice"]


@pytest.fixture
def bob(alice_and_bob):
    return alice_and_bob["Bob"]