"""The screens. Textual draws the interface; every picture is pixel art from art.py.
Conversation is typed only: the talk screen is a text box, and Esc leaves."""
from __future__ import annotations

import json
import math
import random
import time

from rich.console import Group
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Input, RichLog, Static, TabbedContent, TabPane

from . import art, cast
from .art import UI
from .llm import Server
from .night import NightFailed
from .world import Game, clock_text

C = cast.CAST

# ====================================================================== bits

class PixelView(Static):
    """A live pixel picture. painter(w_px, h_px, t) returns a Canvas."""

    def __init__(self, painter, fps: float = 12, bg: str = UI["bg"], **kw):
        super().__init__("", **kw)
        self.painter = painter
        self.fps = fps
        self.bg = bg
        self.t0 = time.time()

    def on_mount(self):
        self.set_interval(1 / self.fps, self.redraw)
        self.call_after_refresh(self.redraw)

    def redraw(self):
        w, h = self.size.width, self.size.height * 2
        if w <= 0 or h <= 0:
            return
        cv = self.painter(w, h, time.time() - self.t0)
        if cv is not None:
            self.update(cv.to_text(self.bg))


def town_scale(h: int) -> int:
    """Chunkier pixels when the window is tall, so the town fills it like a diorama."""
    return 2 if h >= 60 else 1


def upscale(cv: art.Canvas, w: int, h: int, s: int) -> art.Canvas:
    if s == 1:
        return cv
    out = art.Canvas(w, h)
    out.blit(cv, 0, out.h - cv.h * s, scale=s)
    return out


def fit(cv: art.Canvas, w: int, h: int, bg: str | None = None, valign: str = "bottom") -> art.Canvas:
    out = art.Canvas(w, h, bg)
    ox = (w - cv.w) // 2
    oy = (out.h - cv.h) if valign == "bottom" else (out.h - cv.h) // 2
    out.blit(cv, ox, max(0, oy) if valign != "bottom" else oy)
    return out


def chip(npc: str | None, text: str | None = None) -> Text:
    if npc is None:
        return Text(f" {text or 'What really happened'} ", style=Style(color=UI["bg"], bgcolor=UI["truth"], bold=True))
    c = C[npc]
    return Text(f" {text or c['name']} ", style=Style(color="#1C1222", bgcolor=c["color"], bold=True))


def heat_bar(game: Game, width: int = 18) -> Text:
    filled = int(round(game.heat * width))
    t = Text()
    for i in range(width):
        col = art.mix(UI["heat"], UI["danger"], i / max(1, width - 1))
        t.append("▮" if i < filled else "▯", Style(color=col if i < filled else UI["panel2"]))
    return t


def status_bar(game: Game) -> Table:
    g = Table.grid(expand=True)
    g.add_column(justify="left", ratio=1)
    g.add_column(justify="center", ratio=2)
    g.add_column(justify="right", ratio=1)
    sun = "☼" if game.clock < 17 else "☾"
    left = Text.assemble((f" {sun} ", f"bold {UI['heat']}"), (f"{cast.GAME_DAY}  ", UI["ink"]),
                         (clock_text(game.clock), f"bold {UI['ink']}"))
    mid = Text.assemble(("Heat  ", UI["dim"]), heat_bar(game), ("  " + game.tier, f"bold {UI['heat'] if game.heat < 0.66 else UI['danger']}"),
                        (f"   {game.believers} believe it", UI["dim"]))
    right = Text.assemble(("Reputation ", UI["dim"]), (str(game.reputation) + " ", f"bold {UI['player']}"))
    g.add_row(left, mid, right)
    return g


def sentence_case(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


# ====================================================================== the app

class RumorMill(App):
    TITLE = "Rumor Mill"
    CSS = f"""
    $bg: {UI['bg']};
    $panel: {UI['panel']};
    $panel2: {UI['panel2']};
    $ink: {UI['ink']};
    $dim: {UI['dim']};
    $rumor: {UI['rumor']};
    $heat: {UI['heat']};
    $truth: {UI['truth']};
    $player: {UI['player']};

    Screen {{ background: $bg; color: $ink; }}
    PixelView {{ width: 1fr; height: 1fr; }}
    .center {{ width: 100%; content-align: center middle; text-align: center; }}
    .dim {{ color: $dim; }}
    .hint {{ color: $dim; text-align: center; width: 100%; height: 1; }}

    /* title */
    #title-art {{ height: 12; }}
    #title-bubbles {{ height: 8; }}
    #tagline {{ height: 2; color: $dim; text-align: center; text-style: italic; }}
    #load {{ height: 3; text-align: center; }}

    /* night */
    #night-caption {{ height: 3; text-align: center; color: $dim; text-style: italic; padding-top: 1; }}
    #night-town {{ height: 1fr; }}

    /* paper */
    #paper {{ width: 112; max-width: 100%; height: auto; background: {UI['paper']}; color: {UI['paper_ink']}; padding: 1 3; }}
    #paper-wrap {{ align: center middle; height: 1fr; }}
    #masthead {{ height: 4; width: 100%; }}
    #dateline {{ height: 2; }}
    #paper-body {{ height: 13; margin-top: 1; }}
    #paper-photo {{ width: 34; height: 12; }}
    #paper-text {{ width: 1fr; height: auto; padding-left: 2; }}

    /* hub */
    #status {{ height: 1; background: $panel; }}
    #hub-town {{ height: 1fr; min-height: 16; }}
    #labels {{ height: 1; }}
    #town-news {{ height: auto; display: none; padding: 0 1; }}
    #hub-bottom {{ height: 14; }}
    #place-card {{ width: 2fr; background: $panel; padding: 0 1; }}
    #place-face {{ width: 32; height: 100%; }}
    #place-text {{ width: 1fr; padding: 1 1; }}
    #notebook {{ width: 3fr; background: $panel2; padding: 1 2; }}
    #hub-hint {{ height: 1; color: $dim; text-align: center; }}

    /* talk */
    #talk-left {{ width: 32; background: $panel; }}
    #portrait {{ height: 1fr; }}
    #nameplate {{ height: auto; text-align: center; padding-top: 0; }}
    #stage {{ height: 2; text-align: center; color: $dim; text-style: italic; }}
    #talk-right {{ width: 1fr; padding: 0 2; }}
    #talk-head {{ height: 2; }}
    #banner {{ height: auto; display: none; padding: 0 1; margin-bottom: 1; }}
    #transcript {{ height: 1fr; background: $bg; scrollbar-size-vertical: 1; }}
    #bubble {{ height: auto; min-height: 5; border: round $rumor; padding: 0 1; background: $panel; }}
    #say {{ margin-top: 1; border: tall $panel2; background: $panel; }}
    #say:focus {{ border: tall $player; }}
    #talk-hint {{ height: 1; color: $dim; }}

    /* payoff */
    #payoff-left {{ width: 32; background: $panel; }}
    #payoff-right {{ width: 1fr; padding: 1 2; }}
    .card {{ height: auto; background: $panel; border: round $panel2; padding: 0 1; margin-bottom: 1; }}
    .card:hover {{ border: round $rumor; }}
    .card:focus {{ border: round $rumor; background: $panel2; }}
    #cards {{ height: auto; }}
    #scene {{ height: auto; margin-top: 1; }}
    #caption-art {{ height: 6; display: none; margin-top: 1; }}

    /* replay */
    #replay {{ padding: 1 4; }}
    #replay-rows {{ height: auto; }}
    #score {{ height: auto; margin-top: 1; }}

    /* freeze frame */
    FreezeFrame {{ align: center middle; background: rgba(20, 14, 30, 0.85); }}
    #freeze {{ width: 100%; height: 14; }}
    #freeze-cap {{ width: 100%; text-align: center; text-style: bold; height: auto; padding: 0 8; }}

    /* stocks */
    #stocks {{ height: 2fr; }}
    #stocks-text {{ height: auto; padding: 1 6; text-align: center; }}

    /* dm view */
    DMScreen {{ background: $bg; }}
    #dm-head {{ height: 1; }}
    DMScreen TabbedContent {{ height: 1fr; }}
    DMScreen TabPane {{ height: 1fr; padding: 0; }}
    DataTable {{ background: $bg; height: 1fr; }}
    """

    BINDINGS = [
        Binding("f2", "dm_view", "DM view", priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def __init__(self, dm: bool = False):
        super().__init__()
        self.dm = dm  # the DM view is for the instructor only: python rumormill.py --dm
        self.server = Server()
        self.game: Game | None = None

    def on_mount(self):
        self.push_screen(TitleScreen())

    def action_dm_view(self):
        if self.dm and self.game and self.game.p and not isinstance(self.screen, DMScreen):
            self.push_screen(DMScreen())

    def on_unmount(self):
        self.server.stop()


# ====================================================================== title

class TitleScreen(Screen):
    BINDINGS = [Binding("enter", "start", "Start")]

    def compose(self) -> ComposeResult:
        yield Static("", classes="dim")
        yield PixelView(self.paint_title, fps=8, id="title-art")
        yield Static("A comedy detective game about Telephone.\nSomeone in town is telling stories about you.", id="tagline")
        yield PixelView(self.paint_bubbles, fps=10, id="title-bubbles")
        yield Static("", id="load")
        if self.app.dm:
            yield Static("DM mode: F2 opens the DM view at any time: the night shift, every agent call, the chain and the ledger.",
                         classes="hint")
        yield Static("Ctrl+Q quits.", classes="hint")

    def on_mount(self):
        self.ready = False
        self.spin = 0
        self.set_interval(0.15, self.tick)
        self.load()

    def paint_title(self, w, h, t):
        scale = 3 if w >= 190 else 2 if w >= 125 else 1
        word = art.word_canvas("RUMOR MILL", UI["rumor"], art.PAL["P"], scale=scale, shadow="#120E2A")
        cv = fit(word, w, h, None, valign="middle")
        # a glint of light sweeps across the letters
        gx = int((t * 40) % (w + 60)) - 30
        for y in range(cv.h):
            for x in range(gx - 2, gx + 2):
                if cv.get(x - y // 2, y) is not None:
                    cv.blend(x - y // 2, y, "#FFFFFF", 0.35)
        return cv

    def paint_bubbles(self, w, h, t):
        """Five speech bubbles, one in each cast member's color: the town, gossiping."""
        cv = art.Canvas(w, h)
        n, gap = 5, 10
        total = n * 8 + (n - 1) * gap
        x0 = (w - total) // 2
        for i, key in enumerate(cast.KEYS):
            b = art.icon("bubble", {"w": C[key]["color"]})
            bob = int(round(math.sin(t * 3 + i * 0.9) * 1.5))
            cv.blit(b, x0 + i * (8 + gap), (cv.h - 8) // 2 + bob)
        return cv

    def tick(self):
        self.spin += 1
        if self.ready:
            return
        dots = "•" * (1 + self.spin % 3)
        self.query_one("#load", Static).update(Text.assemble(("Waking up the town's gossips ", UI["dim"]), (dots, UI["rumor"])))

    @work(thread=True)
    def load(self):
        ok = self.app.server.start()
        self.app.call_from_thread(self.loaded, ok)

    def loaded(self, ok: bool):
        srv = self.app.server
        if ok:
            self.ready = True
            msg = Text.assemble(("The town is ready.\n", UI["truth"]), ("Press Enter to start the night.", f"bold {UI['ink']}"))
        else:
            # There is no scripted version to fall back to: without the model, the game doesn't start.
            self.ready = False
            msg = Text.assemble(("The game's AI couldn't start, so the game can't run.\n", f"bold {UI['danger']}"),
                                (srv.error or "Unknown error.", UI["dim"]), ("\nCtrl+Q quits.", UI["dim"]))
        self.query_one("#load", Static).update(msg)

    def action_start(self):
        if not self.ready:
            return
        self.app.game = Game(self.app.server)
        self.app.switch_screen(NightScreen())


# ====================================================================== night

class NightScreen(Screen):
    """Only the sleeping town. Everything the night shift does stays hidden (the DM view has it)."""
    BINDINGS = [Binding("enter", "morning", "Morning")]

    def compose(self) -> ComposeResult:
        yield Static("", id="night-caption")
        yield PixelView(self.paint, fps=15, id="night-town")

    def on_mount(self):
        self.done = False
        self.spin = 0
        self.timer = self.set_interval(0.4, self.tick)
        self.tick()
        self.run_night()

    def tick(self):
        self.spin += 1
        n, of = getattr(self, "step", (0, 0))
        count = f"The town is gossiping... {n} of {of}  " if of else "The town is gossiping...  "
        self.query_one("#night-caption", Static).update(Text.assemble(
            ("Wednesday night. While you sleep, the town gossips.\n", Style(italic=True, color=UI["dim"])),
            (count, UI["ink"]), ("•" * (1 + self.spin % 3), UI["rumor"])))

    def on_step(self, entry: dict):
        self.step = (entry.get("n", 0), entry.get("of", 0))

    def paint(self, W, H, t):
        s = town_scale(H)
        w, h = (W + s - 1) // s, (H + s - 1) // s
        g = self.app.game
        roof = g.p["town"]["roof_prop"] if g and g.p else None
        return upscale(art.town(w, h, t, night=True, roof_prop=roof), W, H, s)

    def finished(self):
        self.timer.stop()
        self.done = True
        self.query_one("#night-caption", Static).update(Text.assemble(
            (f"{cast.GAME_DAY} morning. A rumor found its way to your door.\n", f"bold {UI['ink']}"),
            ("Press Enter to read the paper.", UI["dim"])))

    def failed(self, msg: str):
        self.timer.stop()
        self.query_one("#night-caption", Static).update(Text.assemble(
            ("The night shift couldn't build a hunt that can be solved, so it stopped.\n", f"bold {UI['danger']}"),
            (msg[:200] + "  Ctrl+Q quits.", UI["dim"])))

    @work(thread=True)
    def run_night(self):
        game = self.app.game
        try:
            game.night(progress=lambda e: self.app.call_from_thread(self.on_step, e))
        except NightFailed as e:
            self.app.call_from_thread(self.failed, str(e))
            return
        except Exception as e:
            self.app.call_from_thread(self.failed, f"{type(e).__name__}: {e}")
            raise
        self.app.call_from_thread(self.finished)

    def action_morning(self):
        if self.done:
            self.app.game.start_day()
            self.app.switch_screen(MorningScreen())


# ====================================================================== morning

def suspect_poster(w, h, t):
    """The paper's artist's impression of the suspect: a silhouette and a question mark."""
    cv = art.Canvas(w, h, UI["paper"])
    cx = w // 2
    for y in range(h):
        for x in range(w):
            d = math.hypot((x - cx) / 6.5, (y - 9) / 6.5)
            if d < 1:
                cv.set(x, y, "#3A3040")
            if y > 14 and abs(x - cx) < 4 + (y - 14) * 0.9:
                cv.set(x, y, "#3A3040")
    q = art.word_canvas("?", "#FF7AA8", "#D9488A", scale=1)
    cv.blit(q, cx - 2, 6 + int(round(math.sin(t * 2))))
    return cv


class MorningScreen(Screen):
    BINDINGS = [Binding("enter", "next", "Continue")]

    def compose(self) -> ComposeResult:
        with Vertical(id="paper-wrap"):
            with Vertical(id="paper"):
                yield PixelView(self.paint_masthead, fps=1, bg=UI["paper"], id="masthead")
                yield Static("", id="dateline")
                with Horizontal(id="paper-body"):
                    yield PixelView(suspect_poster, fps=4, bg=UI["paper"], id="paper-photo")
                    yield Static("", id="paper-text")
        yield Static("Press Enter.", classes="hint")

    def paint_masthead(self, w, h, t):
        word = art.word_canvas("THE DAILY WHISPER", UI["paper_ink"], "#5A4A60", scale=1)
        return fit(word, w, h, None, valign="middle")

    def on_mount(self):
        game = self.app.game
        cr = game.morning["crier"]
        self.query_one("#dateline", Static).update(Text.assemble(
            (f"{cast.GAME_DAY} edition", "italic #5A4A60"), (f"        {game.p['town']['street']}", "italic #5A4A60"),
            ("\n" + "─" * 104, "#B9AA9A")))
        body = Text()
        body.append(cr["headline"].upper() + "\n\n", Style(bold=True, color=UI["paper_ink"]))
        body.append(cr["subhead"] + "\n\n", Style(italic=True, color="#4A3D52"))
        body.append("Left: " + cr["caption"], Style(color="#6A5D72"))
        self.query_one("#paper-text", Static).update(body)

    def action_next(self):
        self.app.switch_screen(TalkScreen(self.app.game.messenger, hook=True))


# ====================================================================== freeze frame

class FreezeFrame(ModalScreen):
    BINDINGS = [Binding("enter", "close", "Continue"), Binding("escape", "close", "Continue")]

    def __init__(self, big: str, caption: str, color: str):
        super().__init__()
        self.big, self.caption, self.color = big, caption, color

    def compose(self) -> ComposeResult:
        yield PixelView(self.paint, fps=20, bg="#140E1E", id="freeze")
        yield Static(Text(self.caption, Style(bold=True, color=UI["ink"])), id="freeze-cap")
        yield Static("Press Enter.", classes="hint")

    def paint(self, w, h, t):
        scale = 3 if w > 160 else 2
        word = art.word_canvas(self.big, self.color, art.mix(self.color, "#000000", 0.35), scale=scale, shadow="#000000")
        cv = fit(word, w, h, "#140E1E", valign="middle")
        flash = max(0.0, 1.0 - t * 3.5)
        if flash > 0:
            for y in range(cv.h):
                for x in range(cv.w):
                    cv.blend(x, y, "#FFFFFF", flash)
        for i in range(6):   # speed lines
            y = int((i * 7 + t * 20) % cv.h)
            for x in range(0, 6 + i * 2):
                cv.blend(x, y, self.color, 0.4)
                cv.blend(cv.w - 1 - x, (y + 9) % cv.h, self.color, 0.4)
        return cv

    def action_close(self):
        self.dismiss(True)


# ====================================================================== talking

class TalkScreen(Screen):
    """A text box. Type whatever you want; Esc leaves."""
    BINDINGS = [Binding("escape", "leave", "Leave", show=False),
                Binding("enter", "advance", "Continue", show=False)]

    def __init__(self, npc: str, hook: bool = False):
        super().__init__()
        self.npc = npc
        self.hook = hook

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="talk-left"):
                yield PixelView(self.paint_portrait, fps=12, id="portrait")
                yield Static("", id="nameplate")
                yield Static("", id="stage")
            with Vertical(id="talk-right"):
                yield Static("", id="talk-head")
                yield Static("", id="banner")
                yield RichLog(id="transcript", wrap=True, markup=False, highlight=False)
                yield Static("", id="bubble")
                yield Input(placeholder="Say something...", id="say")
                yield Static("", id="talk-hint")

    # setup ---------------------------------------------------------------
    def on_mount(self):
        c = C[self.npc]
        self.game: Game = self.app.game
        self.face = "rest"
        self.full = ""
        self.shown = 0
        self.busy = False
        self.waiting = not self.hook
        self.flushed = True
        self.after_hook = False
        self.pending_event = None
        self.blink_at = time.time() + 3
        self.scale = 1
        self.set_interval(1 / 30, self.type_tick)
        self.query_one("#nameplate", Static).update(Text.assemble(
            (c["name"] + "\n", f"bold {c['color']}"), (sentence_case(self.game.roles[self.npc]["job"]), UI["dim"])))
        self.query_one("#say", Input).placeholder = f"Say something to {c['short']}, then press Enter..."
        self._head()
        if self.hook:
            self.query_one("#say").display = False
            self.query_one("#talk-head", Static).update(Text.assemble(
                (f"{cast.GAME_DAY} morning, outside your door. ", f"bold {UI['ink']}"),
                (f"{c['short']} hurries up the street toward you.", UI["dim"])))
            self.show_reply(self.game.morning["hook"])
        else:
            self.query_one("#talk-hint", Static).update(Text("Type anything: talk, ask, look around. Enter says it. Esc leaves.", UI["dim"]))
            self._lock(True)
            self.do_visit()

    def on_resize(self, event):
        big = self.size.height >= 42 and self.size.width >= 150
        self.scale = 2 if big else 1
        self.query_one("#talk-left").styles.width = 64 if big else 32

    def _head(self):
        g = self.game
        if self.hook:
            return
        left = cast.TURNS_PER_VISIT - g.turns
        dots = Text()
        for i in range(cast.TURNS_PER_VISIT):
            dots.append("● " if i < left else "○ ", UI["player"] if i < left else UI["panel2"])
        head = Table.grid(expand=True)
        head.add_column(ratio=1)
        head.add_column(justify="right")
        head.add_row(Text.assemble((g.place(self.npc), f"bold {UI['ink']}"), (f"   {clock_text(g.clock)}", UI["heat"]),
                                   (f"   {g.tier}", UI["danger"] if g.heat >= 0.66 else UI["dim"])),
                     Text.assemble(("Lines left  ", UI["dim"]), dots))
        self.query_one("#talk-head", Static).update(head)

    def _lock(self, busy: bool):
        self.busy = busy
        if self.hook:
            return
        out = self.game.out_of_turns or self.game.outcome == "busted"
        self.query_one("#say", Input).disabled = busy or out

    # portrait --------------------------------------------------------------
    def paint_portrait(self, w, h, t):
        now = time.time()
        blink = False
        if now >= self.blink_at:
            blink = True
            if now >= self.blink_at + 0.14:
                self.blink_at = now + 2.5 + random.random() * 3
        talking = self.shown < len(self.full)
        face = self.face
        mouth = True
        if talking:
            mouth = int(now * 9) % 2 == 0
            if face == "rest":
                face = "talking"
        elif face == "talking":
            face = "rest"
        if self.waiting:
            face = "rest"
        pc = art.portrait(self.npc, face, mouth_open=mouth, blink=blink and face not in ("shocked", "busted"),
                          spotlight=C[self.npc]["color"])
        cv = art.Canvas(w, h, UI["panel"])
        s = self.scale
        bob = int(round(math.sin(t * 2.2) * 0.6)) if talking else 0
        cv.blit(pc, (w - pc.w * s) // 2, cv.h - pc.h * s + bob, scale=s)
        return cv

    # typewriter --------------------------------------------------------------
    def type_tick(self):
        if self.shown < len(self.full):
            self.shown = min(len(self.full), self.shown + 1)
            self._paint_bubble()
            if self.shown >= len(self.full):
                self.on_line_done()
        elif self.waiting:
            self._paint_bubble()

    def _paint_bubble(self):
        c = C[self.npc]
        t = Text()
        if self.waiting:
            n = int(time.time() * 3) % 4
            t.append(f"{c['short']} is thinking", UI["dim"])
            t.append(" " + "• " * n, c["color"])
        else:
            t.append(self.full[: self.shown], Style(italic=True, color=UI["truth"]) if getattr(self, "narr", False) else UI["ink"])
            if self.shown < len(self.full):
                t.append("▌", c["color"])
        self.query_one("#bubble", Static).update(t)

    def flush_line(self):
        """Move the line in the bubble into the transcript, once."""
        c = C[self.npc]
        if self.full and not self.flushed:
            if getattr(self, "narr", False):
                self.query_one("#transcript", RichLog).write(Text(self.full, Style(italic=True, color=UI["truth"])))
            else:
                self.query_one("#transcript", RichLog).write(Text.assemble((c["short"] + ": ", f"bold {c['color']}"), (self.full, UI["ink"])))
        self.flushed = True

    def show_reply(self, reply: dict):
        c = C[self.npc]
        self.flush_line()
        self.waiting = False
        self.flushed = False
        self.narr = bool(reply.get("narration"))
        self.full = reply["line"]
        self.shown = 0
        self.face = reply.get("face", "talking")
        anim = cast.ANIM_TEXT.get(reply.get("anim", ""), "")
        self.query_one("#stage", Static).update(Text(f"{c['short']} {anim}" if anim else "", Style(italic=True, color=UI["dim"])))

    def on_line_done(self):
        if self.hook:
            self.after_hook = True
            self.flush_line()
            self.query_one("#bubble", Static).update(Text.assemble(
                ("You: ", f"bold {UI['player']}"), ("Oh yeah? I'll get to the bottom of this.\n\n", UI["ink"]),
                ("Press Enter to head into town.", UI["dim"])))
            self.face = "shocked"
            return
        if self.pending_event:
            ev, self.pending_event = self.pending_event, None
            self.run_event(ev)
        self._lock(False)
        if self.game.out_of_turns:
            self.banner(f"{C[self.npc]['short']} has to get back to work. Esc to leave.", UI["heat"])
        elif self.game.last_call:
            self.banner("It's 6 PM. This is your last conversation before the rumor hits Scandal.", UI["danger"])
        self._head()
        say = self.query_one("#say", Input)
        if not say.disabled:
            say.focus()

    def banner(self, text: str, color: str):
        b = self.query_one("#banner", Static)
        b.update(Text(text, Style(bold=True, color=UI["bg"], bgcolor=color)))
        b.styles.background = color
        b.display = True

    def run_event(self, reply):
        ev = reply.get("event")
        short = C[self.npc]["short"]
        if ev == "found":
            self.banner("You found something. It's in your pocket now.", UI["truth"])
        elif ev == "corrected":
            self.banner(f"Evidence can't change. {short} doesn't believe the rumor anymore.", UI["truth"])
        elif ev == "not_caught":
            # the same words for everyone: the judge's reason would hint at the lie (it's in the DM view)
            self.banner(f"It doesn't stick. {short} isn't budging.", UI["heat"])
        elif ev == "cracked":
            t = C[reply["covering_for"]]["short"]
            self.banner(f"{short} cracked.", UI["rumor"])
            self.app.push_screen(FreezeFrame("CRACKED!", f"Yep. {short} was covering for {t}.", UI["rumor"]))
        elif ev == "busted":
            def go(_):
                self.app.switch_screen(PayoffScreen())
            cap = reply.get("caption") or f"Yep. That's {short}. They started it."
            if reply.get("truth"):
                self.query_one("#transcript", RichLog).write(
                    Text(f"What really happened: {reply['truth']}", Style(italic=True, color=UI["truth"])))
                cap += f"\n\nWhat really happened: {reply['truth']}"
            self.app.push_screen(FreezeFrame("BUSTED!", cap, UI["heat"]), go)

    # actions -------------------------------------------------------------------
    @work(thread=True)
    def do_visit(self):
        reply = self.game.visit(self.npc)
        self.app.call_from_thread(self._head)
        self.app.call_from_thread(self.show_reply, reply)

    @work(thread=True)
    def do_say(self, text: str):
        reply = self.game.talk(self.npc, text)
        self.app.call_from_thread(self._after, reply)

    def _after(self, reply):
        if reply.get("event"):
            self.pending_event = reply
        self.show_reply(reply)
        self._head()

    @on(Input.Submitted, "#say")
    def submitted(self, event: Input.Submitted):
        text = event.value.strip()
        if not text or self.busy or self.hook:
            return
        event.input.value = ""
        self._lock(True)
        self.flush_line()
        self.waiting = True
        self.query_one("#transcript", RichLog).write(Text.assemble(("You: ", f"bold {UI['player']}"), (text, UI["player"])))
        self.query_one("#banner", Static).display = False
        self.do_say(text)

    def action_advance(self):
        if self.hook and self.after_hook:
            self.app.switch_screen(HubScreen())

    def action_leave(self):
        if self.hook or self.busy:
            return
        if self.game.outcome == "busted":
            return
        self.game.leave()
        if self.game.outcome == "scandal":
            self.app.switch_screen(LoseScreen())
        else:
            self.app.switch_screen(HubScreen(select=self.npc))


# ====================================================================== hub

class HubScreen(Screen):
    BINDINGS = [
        Binding("left", "move(-1)", "Left", show=False), Binding("right", "move(1)", "Right", show=False),
        Binding("enter", "visit", "Visit"),
        Binding("1", "pick(0)", show=False), Binding("2", "pick(1)", show=False), Binding("3", "pick(2)", show=False),
        Binding("4", "pick(3)", show=False), Binding("5", "pick(4)", show=False),
        Binding("up", "read(-1)", show=False), Binding("down", "read(1)", show=False),
        Binding("pageup", "read(-5)", show=False), Binding("pagedown", "read(5)", show=False),
    ]
    selected = 0

    def __init__(self, select: str | None = None):
        super().__init__()
        self.select_key = select

    def compose(self) -> ComposeResult:
        yield Static("", id="status")
        yield PixelView(self.paint, fps=12, id="hub-town")
        yield Static("", id="labels")
        yield Static("", id="town-news")
        with Horizontal(id="hub-bottom"):
            with Horizontal(id="place-card"):
                yield PixelView(self.paint_face, fps=6, bg=UI["panel"], id="place-face")
                yield Static("", id="place-text")
            with VerticalScroll(id="notebook"):
                yield Static("", id="notebook-text")
        yield Static("Left and right (or 1 to 5) to choose.  Up and down to read your notebook.  Enter to go talk, which takes an hour."
                     + ("  F2 for the DM view." if self.app.dm else ""), id="hub-hint")

    def on_mount(self):
        self.game: Game = self.app.game
        if self.select_key:
            self.selected = cast.KIT_ORDER.index(self.game.roles[self.select_key]["building"])
        else:
            self.selected = cast.KIT_ORDER.index(self.game.roles[self.game.messenger]["building"])
        self.query_one("#notebook").can_focus = False   # keep the arrow keys on the town
        self.news()
        self.refresh_all()

    def on_screen_resume(self):
        self.refresh_all()

    def on_resize(self, event):
        self.refresh_all()

    def news(self):
        """What the town did, and the Director's push, since you last looked."""
        events = self.game.hub_events()
        if not events:
            return
        t = Text()
        for e in events:
            if e["kind"] == "escalation":
                t.append(("The town acts. " if e["tier"] == "whispers" else "Talk of the Town. ") , f"bold {UI['danger']}")
                t.append(e["text"] + "\n", UI["ink"])
            else:
                t.append("You overhear someone in the street: ", f"bold {UI['heat']}")
                t.append(f'"{e["text"]}"\n', Style(italic=True, color=UI["ink"]))
        box = self.query_one("#town-news", Static)
        box.update(t)
        box.display = True

    def key_at(self, i: int) -> str:
        return self.game.who_at(cast.KIT_ORDER[i])

    def paint(self, W, H, t):
        g = self.game
        s = town_scale(H)
        w, h = (W + s - 1) // s, (H + s - 1) // s
        cv = art.town(w, h, t, night=g.clock >= 17, heat=g.heat, selected=self.selected,
                      posters=g.posters, guard=g.guard, roof_prop=g.p["town"]["roof_prop"])
        return upscale(cv, W, H, s)

    def paint_face(self, w, h, t):
        key = self.key_at(self.selected)
        cv = art.portrait(key, "rest", blink=int(t * 10) % 37 == 0, spotlight=C[key]["color"], pad=1)
        return fit(cv, w, h, UI["panel"])

    def refresh_all(self):
        g = self.game
        self.query_one("#status", Static).update(status_bar(g))
        w = self.query_one("#labels").size.width or 120
        slot_w = w // 5
        lab = Text()
        for i, b in enumerate(cast.KIT_ORDER):
            name = f"{i + 1} {g.p['town']['places'][b]['name']}"
            if len(name) > slot_w - 1:
                name = name[: max(4, slot_w - 2)] + "…"
            key = self.key_at(i)
            style = f"bold {UI['bg']} on {C[key]['color']}" if i == self.selected else UI["dim"]
            pad = max(0, slot_w - len(name))
            lab.append(" " * (pad // 2))
            lab.append(name, style)
            lab.append(" " * (pad - pad // 2))
        self.query_one("#labels", Static).update(lab)
        self._place_card()
        self._notebook()

    def _place_card(self):
        g = self.game
        key = self.key_at(self.selected)
        c = C[key]
        b = g.roles[key]["building"]
        t = Text()
        t.append(c["name"] + "\n", f"bold {c['color']}")
        # name and job only: no personality type or fingerprint, so the player learns who people are by talking to them
        t.append(f"{sentence_case(g.roles[key]['job'])}, {g.p['town']['places'][b]['name']}\n\n", UI["dim"])
        if g.visits[key] == 0:
            t.append("You haven't talked to them today.\n", UI["ink"])
        else:
            t.append(f"Talked {g.visits[key]} time{'s' if g.visits[key] > 1 else ''}.", UI["ink"])
            if key in g.cracked:
                t.append("  Cracked.", f"bold {UI['rumor']}")
            if key in g.corrected:
                t.append("  Saw your evidence.", f"bold {UI['truth']}")
            t.append("\n")
        bark = g.bark(key)
        if bark:
            t.append(f'\nAs you pass, {c["short"]} calls out: ', UI["dim"])
            t.append(f'"{bark}"', Style(italic=True, color=UI["ink"]))
        self.query_one("#place-text", Static).update(t)

    def _notebook(self):
        """Word for word what the selected person said to you, and what you said, in order.
        Nothing is worked out for the player: no sources, no chain, no fingerprint matches."""
        g = self.game
        key = self.key_at(self.selected)
        c = C[key]
        out = Text()
        out.append("In your pocket: ", f"bold {UI['truth']}")
        if not g.pocket:
            out.append("nothing yet\n", UI["dim"])
        for ev in g.pocket:
            out.append(f"\n  {ev['title']}\n", UI["truth"])
            for line in ev["lines"]:
                out.append(f"    {line}\n", UI["dim"])
        out.append("\nYour notebook: ", f"bold {UI['ink']}")
        out.append(c["short"] + "\n", f"bold {c['color']}")
        notes = [n for n in g.notes if n["npc"] == key]
        if not notes:
            out.append(f"\nNothing yet. You haven't talked to {c['short']}.\n", UI["dim"])
        last = None
        for n in notes:
            if (n["clock"], n["where"]) != last:
                last = (n["clock"], n["where"])
                out.append(f"\n{clock_text(n['clock'])}, {n['where']}\n", f"bold {UI['dim']}")
            if n["you"]:
                out.append(f"  {n['you']}\n", UI["player"])
            if n.get("narr"):
                out.append(f"  {n['line']}\n", Style(italic=True, color=UI["truth"]))
                continue
            out.append(f"  {c['short']}: ", f"bold {c['color']}")
            out.append(f'"{n["line"]}"\n', Style(italic=True, color=UI["ink"]))
        heard = [n for n in g.notes if n["npc"] is None]
        if heard:
            out.append("\nOverheard in the street\n", f"bold {UI['heat']}")
            for n in heard:
                out.append(f"  {clock_text(n['clock'])}: ", UI["dim"])
                out.append(f'"{n["line"]}"\n', Style(italic=True, color=UI["ink"]))
        self.query_one("#notebook-text", Static).update(out)
        self.call_after_refresh(self.query_one("#notebook").scroll_end, animate=False)

    def action_read(self, d: int):
        self.query_one("#notebook").scroll_relative(y=d * 2, animate=False)

    def action_move(self, d: int):
        self.selected = (self.selected + d) % 5
        self.refresh_all()

    def action_pick(self, i: int):
        self.selected = i
        self.refresh_all()

    def action_visit(self):
        self.app.switch_screen(TalkScreen(self.key_at(self.selected)))


# ====================================================================== payoff

class Card(Static, can_focus=True):
    def __init__(self, idx: int, option: dict, **kw):
        super().__init__("", classes="card", **kw)
        self.idx = idx
        self.option = option

    def on_mount(self):
        o = self.option
        grid = Table.grid(padding=(0, 2))
        grid.add_column(width=10)
        grid.add_column(ratio=1)
        ic = None
        for p in o["props"]:
            ic = art.icon(p)
            if ic:
                break
        pic = ic.to_text(UI["panel"]) if ic else Text("  " + str(self.idx + 1), f"bold {UI['rumor']}")
        body = Text()
        body.append(f"{self.idx + 1}  {o['title']}\n", f"bold {UI['ink']}")
        body.append(o["description"] + "\n", UI["ink"])
        body.append("props: " + ", ".join(p.replace("_", " ") for p in o["props"]), Style(italic=True, color=UI["dim"]))
        grid.add_row(pic, body)
        self.update(grid)

    def on_click(self):
        self.screen.choose(self.idx)

    def key_enter(self):
        self.screen.choose(self.idx)


class PayoffScreen(Screen):
    BINDINGS = [Binding("1", "choose(0)", show=False), Binding("2", "choose(1)", show=False),
                Binding("3", "choose(2)", show=False), Binding("enter", "next", show=False)]

    def compose(self) -> ComposeResult:
        g = self.app.game
        c = C[g.source]
        with Horizontal():
            with Vertical(id="payoff-left"):
                yield PixelView(self.paint, fps=12, id="portrait")
                yield Static(Text.assemble((c["name"] + "\n", f"bold {c['color']}"),
                                           (sentence_case(g.roles[g.source]["job"]), UI["dim"])), id="nameplate")
            with VerticalScroll(id="payoff-right"):
                yield Static("", id="payoff-head")
                yield Vertical(id="cards")
                yield Static("", id="scene")
                yield PixelView(self.paint_caption, fps=15, id="caption-art")
                yield Static("", id="payoff-hint", classes="hint")

    def on_mount(self):
        self.game: Game = self.app.game
        self.short = C[self.game.source]["short"]
        self.face = "busted"
        self.phase = "menu"
        self.beats: list = []
        self.beat_i = 0
        self.typed = 0
        self.caption = ""
        self.cap_t = 0.0
        self.scale = 1
        self._hold = None
        self.query_one("#payoff-head", Static).update(Text.assemble(
            (f"{cast.GAME_DAY} evening. The confrontation.\n", f"bold {UI['ink']}"),
            (f"{self.short} started it, and {self.short} is all yours. Three comeuppances are being written", UI["dim"])))
        self.set_interval(1 / 30, self.tick)
        self.load_menu()

    def on_resize(self, event):
        big = self.size.height >= 42 and self.size.width >= 150
        self.scale = 2 if big else 1
        self.query_one("#payoff-left").styles.width = 64 if big else 32

    def paint(self, w, h, t):
        talking = self.phase == "scene" and self.beat_i < len(self.beats) and self.typed < len(self.beats[self.beat_i]["text"])
        key = self.game.source
        pc = art.portrait(key, self.face, mouth_open=int(t * 9) % 2 == 0 if talking else True, spotlight=C[key]["color"])
        cv = art.Canvas(w, h, UI["panel"])
        cv.blit(pc, (w - pc.w * self.scale) // 2, cv.h - pc.h * self.scale, scale=self.scale)
        return cv

    def paint_caption(self, w, h, t):
        if not self.caption:
            return art.Canvas(w, h)
        dt = time.time() - self.cap_t
        word = art.word_canvas(self.caption, UI["ink"], UI["dim"], scale=1, shadow="#120E2A")
        cv = fit(word, w, h, None, valign="middle")
        flash = max(0.0, 1 - dt * 3)
        if flash:
            for y in range(cv.h):
                for x in range(cv.w):
                    cv.blend(x, y, "#FFFFFF", flash)
        return cv

    @work(thread=True)
    def load_menu(self):
        options, src = self.game.rewards()
        self.app.call_from_thread(self.show_menu, options)

    def show_menu(self, options):
        cards = self.query_one("#cards", Vertical)
        for i, o in enumerate(options):
            cards.mount(Card(i, o))
        self.query_one("#payoff-head", Static).update(Text.assemble(
            (f"{cast.GAME_DAY} evening. The confrontation.\n", f"bold {UI['ink']}"),
            (f"{self.short} started it, and {self.short} is all yours. Pick the comeuppance (1, 2 or 3).", UI["dim"])))
        self.call_after_refresh(lambda: self.query(Card).first().focus())

    def action_choose(self, i: int):
        self.choose(i)

    def choose(self, i: int):
        if self.phase != "menu" or not self.query(Card):
            return
        self.phase = "loading"
        for card in self.query(Card):
            if card.idx != i:
                card.display = False
        self.query_one("#scene", Static).update(Text("The Scene Director is setting up the shot...", UI["dim"]))
        self.face = "shocked"
        self.perform(i)

    @work(thread=True)
    def perform(self, i: int):
        scene, src = self.game.perform(i)
        self.app.call_from_thread(self.start_scene, scene)

    def start_scene(self, scene):
        self.beats = scene["beats"]
        self.final_caption = scene["caption"]
        self.beat_i = 0
        self.typed = 0
        self.phase = "scene"

    def tick(self):
        if self.phase != "scene" or self.beat_i >= len(self.beats):
            return
        beat = self.beats[self.beat_i]
        if self.typed < len(beat["text"]):
            self.typed += 1
        elif self._hold is None:
            self._hold = time.time()
        elif time.time() - self._hold > 1.0:
            self._hold = None
            self.beat_i += 1
            self.typed = 0
            self.face = ["shocked", "crying", "busted", "crying"][min(3, self.beat_i)]
            if self.beat_i >= len(self.beats):
                self.phase = "done"
                self.caption = self.final_caption.upper()
                self.cap_t = time.time()
                self.query_one("#caption-art").display = True
                self.query_one("#payoff-hint", Static).update(Text("Press Enter for the replay.", UI["dim"]))
        self._render_scene()

    def _render_scene(self):
        t = Text()
        for i, b in enumerate(self.beats[: self.beat_i + 1]):
            text = b["text"] if i < self.beat_i else b["text"][: self.typed]
            t.append(f"{cast.SHOT_TEXT.get(b['shot'], b['shot'])}\n", Style(italic=True, color=UI["heat"]))
            t.append(text + "\n\n", UI["ink"])
        if self.phase == "done":
            t.append(self.final_caption + "\n", f"bold {UI['ink']}")
        self.query_one("#scene", Static).update(t)

    def action_next(self):
        if self.phase == "done":
            self.app.switch_screen(ReplayScreen())


# ====================================================================== lose

class LoseScreen(Screen):
    BINDINGS = [Binding("enter", "next", "Continue")]

    def compose(self) -> ComposeResult:
        g = self.app.game
        line = g.morning["escalation"]["scandal"]["line"]
        yield PixelView(lambda w, h, t: art.stocks_scene(w, h, t), fps=15, id="stocks")
        yield Static(Text.assemble(("SCANDAL\n\n", f"bold {UI['danger']}"), (line + "\n\n", UI["ink"]),
                                   (f"Reputation {cast.REP_START} → {g.reputation}.   Press Enter for the replay.", UI["dim"])),
                     id="stocks-text")

    def on_mount(self):
        self.app.game.save_actions()

    def action_next(self):
        self.app.switch_screen(ReplayScreen())


# ====================================================================== replay

MUT_TEXT = {"add detail": "added a detail", "merge": "merged in another rumor", "exaggerate": "exaggerated it",
            "swap name on purpose": "swapped the name on purpose", "the truth": "the truth"}

class ReplayScreen(Screen):
    BINDINGS = [Binding("enter", "dm", "DM view")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="replay"):
            yield Static(Text("The chain, played back", f"bold {UI['ink']}"))
            yield Static(Text("Each hop changed exactly one thing. Struck words were dropped, bright words were added.\n", UI["dim"]))
            yield Static("", id="replay-rows")
            yield Static("", id="score")

    def on_mount(self):
        self.game: Game = self.app.game
        self.rows = self.game.replay_rows()
        self.n = 0
        self.timer = self.set_interval(1.3, self.reveal)
        self.reveal()

    def reveal(self):
        self.n += 1
        out = Text()
        for r in self.rows[: self.n]:
            npc = r["npc"]
            color = UI["truth"] if npc is None else C[npc]["color"]
            out.append_text(chip(npc))
            out.append("  " + MUT_TEXT.get(r["mutation"], r["mutation"]), Style(italic=True, color=UI["dim"]))
            out.append("\n")
            if r["diff"] is None:
                out.append("  " + r["sentence"] + "\n", UI["truth"])
            else:
                out.append("  ")
                for op, words in r["diff"]:
                    if op == "same":
                        out.append(words + " ", UI["ink"])
                    elif op == "del":
                        out.append(words, Style(strike=True, color="#8A6F86"))
                        out.append(" ")
                    else:
                        out.append(words, Style(bold=True, underline=True, color=color))
                        out.append(" ")
                out.append("\n")
            if r["line"]:
                out.append(f'  "{r["line"]}"\n', Style(italic=True, color=UI["dim"]))
            out.append("\n")
        self.query_one("#replay-rows", Static).update(out)
        if self.n >= len(self.rows):
            self.timer.stop()
            self.show_score()

    def show_score(self):
        s = self.game.score()
        won = self.game.outcome == "busted"
        g = Table.grid(padding=(0, 4))
        for _ in range(4):
            g.add_column()

        def stat(big, small, col):
            return Text.assemble((big + "\n", f"bold {col}"), (small, UI["dim"]))
        g.add_row(stat(f"{s['gap']}%", "Biggest Gap: how far\nthe story drifted", UI["rumor"]),
                  stat(str(s["cracked"]), "liars cracked", UI["heat"]),
                  stat(f"{s['hours']} of 9", "hours used", UI["player"]),
                  stat(f"{cast.REP_START} → {s['reputation']}", "reputation", UI["truth"] if won else UI["danger"]))
        short = C[self.game.source]["short"]
        head = Text(f"Rumor busted. {short} wears it now.\n" if won else "The rumor won this time.\n",
                    f"bold {UI['truth'] if won else UI['danger']}")
        tail = Text(("\nEnter opens the DM view (the night shift, every agent call, the chain and the ledger). " if self.app.dm else "\n")
                    + "Ctrl+Q quits.", UI["dim"])
        self.query_one("#score", Static).update(Group(head, g, tail))

    def action_dm(self):
        if self.app.dm:
            self.app.push_screen(DMScreen())


# ====================================================================== DM view

class DMScreen(Screen):
    BINDINGS = [Binding("escape", "close", "Back"), Binding("f2", "close", "Back", priority=True)]

    def compose(self) -> ComposeResult:
        yield Static(Text.assemble((" The DM view  ", f"bold {UI['bg']} on {UI['rumor']}"),
                                   ("   What the AI Dungeon Master is doing behind the curtain. Esc to go back.", UI["dim"])), id="dm-head")
        with TabbedContent():
            with TabPane("Night shift", id="tab-night"):
                yield DataTable(id="night", zebra_stripes=True)
            with TabPane("Agent calls", id="tab-calls"):
                yield DataTable(id="calls", zebra_stripes=True)
            with TabPane("Chain", id="tab-mut"):
                yield DataTable(id="mut", zebra_stripes=True)
            with TabPane("Quest", id="tab-quest"):
                with VerticalScroll():
                    yield Static("", id="quest")
            with TabPane("Ledger", id="tab-ledger"):
                with VerticalScroll():
                    yield Static("", id="ledger")

    def on_mount(self):
        game: Game = self.app.game
        snap = game.ledger.snapshot()
        night = self.query_one("#night", DataTable)
        night.add_columns("step", "LLM or code", "written by", "result")
        for e in snap["night_log"]:
            night.add_row(e["agent"], e["kind"], e["source"], e["result"][:150])
        calls = self.query_one("#calls", DataTable)
        calls.add_columns("time", "agent", "job", "try", "result", "written by", "ms", "tok/s", "note")
        for e in game.server.log:
            self._add_call(e)
        game.server.listeners.append(self._listen)
        mut = self.query_one("#mut", DataTable)
        mut.add_columns("hop", "who", "heard from", "told", "where, when", "change", "field", "before", "after", "check", "written by")
        for e in game.chain:
            before = e["before"] if isinstance(e["before"], str) else "; ".join(e["before"]) or "(none)"
            after = e["after"] if isinstance(e["after"], str) else e["after"][-1]
            told = C[e["told_to"]]["short"] if e["told_to"] else "you"
            mut.add_row(str(e["hop"]), C[e["npc"]]["short"], C[e["heard_from"]]["short"] if e["heard_from"] else "(started it)",
                        told, f"{e['told_where']}, {e['told_when']}"[:50], e["mutation"].replace("_", " "), e["field_changed"],
                        before[:50], after[:50], e["consistency"], e["written_by"])
        self.query_one("#quest", Static).update(self._quest(game))
        self.query_one("#ledger", Static).update(Syntax(json.dumps(snap, indent=2), "json", theme="dracula", word_wrap=True))

    def _quest(self, game: Game) -> Text:
        p = game.p
        H = p["hunt"]
        t = Text()
        t.append(f"Hunt {H['id']}: what really happened\n", f"bold {UI['truth']}")
        t.append(f"  {H['truth']}\n", UI["ink"])
        t.append(f"  Started by {C[p['source']]['name']}, " + ("who lies about it.\n\n" if H["kind"] == "liar"
                                                                  else "by mistake.\n\n"), UI["dim"])
        t.append("Quest steps\n", f"bold {UI['heat']}")
        for s in p["quest"]:
            find = s["find"] if s["find"] == "the source" else C[s["find"]]["short"]
            t.append(f"  {s['step']}. Find {find}, from {C[s['from']]['short']}: {s['how']}\n", UI["ink"])
        t.append("\nThe proof, and where it is\n", f"bold {UI['heat']}")
        for f in H["finds"]:
            t.append(f"  {f['title']} ({p['town']['places'][f['where']]['name']}): " + " / ".join(f["lines"]) + "\n", UI["ink"])
        if p["lies"]:
            t.append("\nThe lie\n", f"bold {UI['rumor']}")
            for k, l in p["lies"].items():
                t.append(f"  {C[k]['short']}: {l['lie']}\n", UI["ink"])
                t.append("    Caught by: " + ", ".join(game.find(f)["title"] for f in l["catch"]) + "\n", UI["dim"])
        crit = game.gate.scores
        if crit:
            t.append(f"\nComedy Critic: {len(crit)} lines scored, average {sum(c['score'] for c in crit) / len(crit):.1f} of 5\n",
                     f"bold {UI['rumor']}")
        return t

    def _listen(self, entry):
        try:
            self.app.call_from_thread(self._add_call, entry)
        except Exception:
            pass

    def _add_call(self, e):
        calls = self.query_one("#calls", DataTable)
        ok = e.get("ok")
        res = Text("pass", UI["truth"]) if ok else Text("sent back", UI["rumor"])
        src = e.get("source", "")
        calls.add_row(e.get("t", ""), e.get("agent", ""), (e.get("label") or "")[:34], str(e.get("attempt", "")), res,
                      Text(src, UI["truth"] if src == "model" else UI["heat"]), str(e.get("ms", "")),
                      str(e.get("tokens_per_sec", "")), (e.get("note") or "")[:70])
        calls.scroll_end(animate=False)

    def on_unmount(self):
        game = self.app.game
        if game and self._listen in game.server.listeners:
            game.server.listeners.remove(self._listen)

    def action_close(self):
        self.app.pop_screen()
