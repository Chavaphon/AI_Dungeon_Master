"""How `play` draws on the terminal (WBS 13.5).

Every line `play` prints goes through a `Screen`, which styles each kind of
output differently: the narration as plain text, the result lines in cyan and
system messages (hints, prompts to rephrase, the end-of-session report) dimmed.
While the model replies it shows "The Dungeon Master is thinking..." with a
spinner.

`--no-color` makes a plain screen, for screen readers and light terminals: the
console emits no ANSI escape codes, every panel is drawn as its title on a line
of its own followed by its text, with no box drawing, and the spinner, whose
animation is made of cursor escape codes, is one line printed once. The screen
is display only: it is never logged or sent to the model (CLAUDE.md section 15,
item 80).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.text import Text

THINKING = "The Dungeon Master is thinking..."

NARRATION = "none"
RESULT = "cyan"
SYSTEM = "dim"


class Screen:
    """The terminal `play` draws on: styled, or plain for `--no-color`."""

    def __init__(self, console: Console, *, plain: bool) -> None:
        self.console = console
        self.plain = plain

    @classmethod
    def make(cls, *, plain: bool) -> Screen:
        """A screen on standard output. A plain one has no colour system, so
        no style reaches the terminal as an escape code."""
        if plain:
            return cls(Console(highlight=False, color_system=None, emoji=False), plain=True)
        return cls(Console(highlight=False), plain=False)

    def narration(self, text: str) -> None:
        self.console.print(text, style=NARRATION, markup=False)

    def result(self, line: str) -> None:
        self.console.print(line, style=RESULT, markup=False)

    def system(self, text: str) -> None:
        self.console.print(text, style=SYSTEM, markup=False)

    def show(self, renderable: RenderableType) -> None:
        """A panel, a group of panels or any other renderable; drawn without
        boxes on a plain screen."""
        self.console.print(flatten(renderable) if self.plain else renderable)

    def blank(self) -> None:
        self.console.print()

    def input(self, prompt: str) -> str:
        return self.console.input(prompt)

    def working(self, message: str = THINKING) -> AbstractContextManager[object]:
        """A spinner with `message` while the block runs; on a plain screen,
        the message once."""
        if self.plain:
            return self._said(message)
        return self.console.status(message)

    @contextmanager
    def _said(self, message: str) -> Iterator[None]:
        self.system(message)
        yield


def flatten(renderable: RenderableType) -> RenderableType:
    """`renderable` with every panel, in groups too, replaced by its title on a
    line of its own, its body, and a blank line."""
    if isinstance(renderable, Panel):
        title = renderable.title
        heading = Text.from_markup(title) if isinstance(title, str) else (title or Text())
        return Group(heading, flatten(renderable.renderable), Text())
    if isinstance(renderable, Group):
        return Group(*(flatten(r) for r in renderable.renderables))
    return renderable
