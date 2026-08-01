"""Single chokepoint for all browser control in the synchronizer.

Every browser call in this package goes through here. It talks to the SAME
centralized Playwright MCP wrapper daemon that Claude Code sessions use
(the isolation middleware on http://localhost:8931/mcp) — there is one browser
stack, not two.

Why `mcporter` is the transport: openclaw crons cannot call the MCP tools
directly because the gateway can't host Playwright's draft-2020-12 schema
(openclaw#70196). `mcporter call playwright.<tool>` is the sanctioned CLI client
to the wrapper. So this module shells out to `mcporter`, but the destination is
the central daemon either way. If a future shared Python client for the wrapper
lands in the using-playwright-mcp skill, swap the body of `_call` to use it and
nothing else in this package changes.

Each `mcporter` invocation runs in its own tab-isolation context, so callers
must `navigate` before `evaluate` within the same logical step.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any


class PlaywrightError(RuntimeError):
    """A browser call failed. Never swallowed into an empty result."""


def _call(tool: str, timeout: int = 90, **kwargs: str) -> str:
    """Run ``mcporter call playwright.<tool> k=v ...`` and return the Result text.

    Raises PlaywrightError on non-zero exit or a missing Result block, so a
    failed fetch can never masquerade as "no data" (Aaron's no-silent-swallow
    rule).
    """
    args = ["mcporter", "call", f"playwright.{tool}"]
    for key, value in kwargs.items():
        args.append(f"{key}={value}")
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise PlaywrightError(f"{tool}: timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise PlaywrightError(
            f"{tool}: exit {proc.returncode}: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return _extract_result(proc.stdout)


_RESULT_HEADER = "### Result"
# mcporter's fixed trailer after the result body. Cutting on THIS (not the next
# "### ") means a result body that itself contains a "### heading" line — e.g. a
# member's markdown comment — is not truncated.
_RESULT_TRAILER = "\n### Ran Playwright code"


def _extract_result(stdout: str) -> str:
    """Pull the text of the ``### Result`` block, robust to ``###`` in the body."""
    idx = stdout.find(_RESULT_HEADER)
    if idx == -1:
        # Some tools (navigate) print no Result block; treat stdout as the body.
        return stdout.strip()
    body = stdout[idx + len(_RESULT_HEADER) :]
    # Cut at the known trailer. rindex so a body containing the literal trailer
    # text keeps everything up to the LAST (real) trailer.
    cut = body.rfind(_RESULT_TRAILER)
    if cut != -1:
        body = body[:cut]
    return body.strip()


def navigate(url: str, timeout: int = 90) -> None:
    """Navigate the cron's isolated tab to ``url``."""
    _call("browser_navigate", url=url, timeout=timeout)


def evaluate(function: str, timeout: int = 90) -> Any:
    """Run a JS ``() => {...}`` function in the page and return parsed JSON.

    Falls back to the raw string when the result is not JSON.
    """
    raw = _call("browser_evaluate", function=function, timeout=timeout)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def fetch(url: str, function: str, *, expect: type = dict, label: str = "fetch") -> Any:
    """Navigate to ``url``, run ``function`` in-page, and return a shape-checked result.

    Centralizes the navigate -> evaluate -> validate sequence used by every read
    path so the error format and shape check live in one place. Raises
    PlaywrightError (never swallows) if the result isn't the expected type.
    """
    navigate(url)
    result = evaluate(function)
    if not isinstance(result, expect):
        raise PlaywrightError(
            f"{label}: expected {expect.__name__}, got {str(result)[:200]}"
        )
    return result


def type_text(
    selector: str, text: str, *, slowly: bool = True, timeout: int = 90
) -> None:
    """Type ``text`` into ``selector`` with real keystrokes.

    Real typing (not JS ``.value`` injection) is required for React-controlled
    inputs like the Meetup comment composer — value injection does not register
    and the post silently no-ops.
    """
    _call(
        "browser_type",
        target=selector,
        text=text,
        slowly="true" if slowly else "false",
        timeout=timeout,
    )


def click(selector: str, timeout: int = 90) -> None:
    """Real-click the element matching ``selector``."""
    _call("browser_click", target=selector, timeout=timeout)
