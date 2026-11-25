"""How `play` draws (WBS 13.5, #253): narration, result lines and system
messages each styled differently, a spinner while the model replies, and a
plain screen for `--no-color` with no ANSI escape codes and no box drawing.

Run: pytest tests/play/test_screen.py -v
"""

import io
import re

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from adm.play.screen import THINKING, Screen, flatten

ESCAPE = "\x1b"
# Box drawing (U+2500-U+257F) and block elements (U+2580-U+259F).
BOXES = re.compile("[─-▟]")


def _screen(*, plain: bool) -> tuple[Screen, io.StringIO]:
    """A screen on a forced terminal, so a style would be an escape code."""
    out = io.StringIO()
    system = None if plain else "standard"
    console = Console(file=out, force_terminal=True, color_system=system, width=80)
    return Screen(console, plain=plain), out


def _draw(screen: Screen) -> None:
    screen.narration("The rat squeals.")
    screen.result("You hit giant rat 1 with your short sword.")
    screen.system("You could try: dodge")
    screen.show(Group(Panel(Text("Lyra: healthy"), title="Status"), Panel("inner")))
    with screen.working():
        pass


def test_the_three_kinds_of_output_are_styled_differently() -> None:
    styles = []
    for say in ("narration", "result", "system"):
        screen, out = _screen(plain=False)
        getattr(screen, say)("words")
        styles.append(out.getvalue().split("words")[0])
    assert len(set(styles)) == 3, styles


def test_a_styled_screen_draws_boxes() -> None:
    screen, out = _screen(plain=False)
    _draw(screen)
    assert ESCAPE in out.getvalue() and BOXES.search(out.getvalue())


def test_a_plain_screen_has_no_escape_codes_and_no_boxes() -> None:
    """The acceptance of #253, for every kind of output and the spinner."""
    screen, out = _screen(plain=True)
    _draw(screen)
    text = out.getvalue()
    assert ESCAPE not in text
    assert BOXES.search(text) is None, BOXES.search(text)
    for shown in ("The rat squeals.", "Status", "Lyra: healthy", "inner", THINKING):
        assert shown in text


def test_the_plain_spinner_is_one_line() -> None:
    screen, out = _screen(plain=True)
    with screen.working("Loading..."):
        pass
    assert out.getvalue() == "Loading...\n"


def test_flatten_puts_each_panel_title_on_its_own_line() -> None:
    console = Console(file=io.StringIO(), width=80, record=True)
    console.print(flatten(Group(Panel("body", title="Inventory"), Panel(Text("more")))))
    assert console.export_text().splitlines() == ["Inventory", "body", "", "", "more", ""]


def test_make_gives_a_plain_screen_no_colour_system() -> None:
    assert Screen.make(plain=True).console.color_system is None
    assert Screen.make(plain=True).plain and not Screen.make(plain=False).plain
