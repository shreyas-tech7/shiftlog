"""The one place that starts a subprocess. Every call needs a timeout.

A test (tests/test_proc.py) scans the source tree and fails if any other file
starts a process, so every child process in gatedcrew goes through `run`.
"""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass


@dataclass
class Result:
    code: int
    out: str
    err: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.timed_out


def run(
    cmd: list[str],
    *,
    timeout: float,
    cwd: str | os.PathLike | None = None,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
    capture: bool = True,
) -> Result:
    """Run `cmd` (a list, never a shell string) and wait at most `timeout` seconds.

    The child gets its own process group, so a timeout kills the whole tree,
    including grandchildren that a worker script may start.
    """
    if timeout is None or timeout <= 0:
        raise ValueError("run() needs a positive timeout")
    if isinstance(cmd, str):
        raise TypeError("run() takes a list, not a shell string")
    pipe = subprocess.PIPE if capture else None
    proc = subprocess.Popen(  # noqa: S603 - argv list, no shell
        cmd,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=pipe,
        stderr=pipe,
        text=True,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(stdin, timeout=timeout)
        return Result(proc.returncode, out or "", err or "")
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        # A grandchild in its own session can keep the pipes open after the kill.
        # Wait a little, then stop reading so the harness never hangs.
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            for pipe_ in (proc.stdout, proc.stderr):
                if pipe_:
                    pipe_.close()
            proc.wait(timeout=5)
            out, err = "", ""
        return Result(-9, out or "", (err or "") + f"\ntimed out after {timeout}s", True)
