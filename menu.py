import time
import os

try:
    import ujson as json
except Exception:
    import json

import amyboard


# -----------------------------
# Configuration
# -----------------------------
DISPLAY_ROTATE = 90  # 0, 90, 180, 270 (used when sh1107 module is available)
INPUT_MODE = "auto"  # "demo", "adafruit", "twist", "auto", "computer", "midi", "hybrid"
CONTROL_SOURCE_OPTIONS = ("hybrid", "computer", "midi", "auto", "adafruit", "twist", "demo")
MIDI_UART_ID = 1
MIDI_BAUD = 31250
MIDI_RX_PIN = None
MIDI_TX_PIN = None
MIDI_NAV_CC = 20
MIDI_SELECT_CC = 21
MIDI_BACK_CC = 22
MIDI_NOTE_SELECT = 60
MIDI_NOTE_BACK = 61
MIDI_NOTE_UP = 62
MIDI_NOTE_DOWN = 63
CONFIG_PATH = "/user/current/perf_config.json"
STATE_PATH = "/user/current/menu_state.json"
PATCH_PROFILE_DIR = "/user/patches"
PATCH_PROFILE_FORMAT = "amyboard-menu-profile"
PATCH_PROFILE_VERSION = 1
DEFAULT_PRESET_SYNTH = 1
BUILTIN_PATCH_MIN = 0
BUILTIN_PATCH_MAX = 257
DEFAULT_CV_PITCH_INPUT = 0  # CV1 in
DEFAULT_CV_GATE_INPUT = 1  # CV2 in
DEFAULT_CV_GATE_ON = 2.5
DEFAULT_CV_GATE_OFF = 1.0
DEFAULT_CV_PITCH_SCALE = 12.0  # 1V/oct -> 12 semitones per volt
DEFAULT_CV_PITCH_OFFSET = 60.0  # 0V = MIDI note 60
DEFAULT_FILTER_TYPE = "LPF"
DEFAULT_FILTER_CUTOFF = 4000  # Hz, audible default


def get_filter_type_options():
    try:
        import amy
    except Exception:
        return ("LPF",)

    options = []
    if hasattr(amy, "FILTER_LPF"):
        options.append("LPF")
    if hasattr(amy, "FILTER_HPF"):
        options.append("HPF")
    if hasattr(amy, "FILTER_BPF"):
        options.append("BPF")
    if hasattr(amy, "FILTER_LPF24"):
        options.append("LPF24")

    if not options:
        return ("LPF",)
    return tuple(options)


FILTER_TYPE_OPTIONS = get_filter_type_options()


# -----------------------------
# Helpers
# -----------------------------
def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def is_dir(path):
    try:
        mode = os.stat(path)[0]
        return (mode & 0x4000) != 0
    except Exception:
        return False


def safe_read_json(path, default):
    try:
        with open(path, "r") as f:
            return json.loads(f.read())
    except Exception:
        return default


def safe_write_json(path, obj):
    try:
        with open(path, "w") as f:
            f.write(json.dumps(obj))
        return True
    except Exception:
        return False


def scan_patch_files(paths):
    out = []
    for p in paths:
        try:
            for ent in os.ilistdir(p):
                name = ent[0]
                full = p + "/" + name
                if name.endswith(".patch"):
                    out.append(full)
                elif is_dir(full):
                    # One level deep is enough for v1
                    try:
                        for sub in os.ilistdir(full):
                            subname = sub[0]
                            if subname.endswith(".patch"):
                                out.append(full + "/" + subname)
                    except Exception:
                        pass
        except Exception:
            pass
    out.sort()
    return out


def short_name(path):
    i = path.rfind("/")
    if i >= 0:
        return path[i + 1 :]
    return path


def deep_copy(value):
    if isinstance(value, dict):
        return {k: deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [deep_copy(v) for v in value]
    return value


def merge_missing(dst, defaults):
    if not isinstance(dst, dict):
        dst = {}
    for k, v in defaults.items():
        if k not in dst:
            dst[k] = deep_copy(v)
        elif isinstance(v, dict):
            dst[k] = merge_missing(dst.get(k), v)
    return dst


def normalize_filter_type(value):
    if not isinstance(value, str):
        value = str(value)
    kind = value.upper().strip()
    if kind in ("LPF", "LOWPASS", "LOW-PASS"):
        return "LPF"
    if kind in ("HPF", "HIGHPASS", "HIGH-PASS"):
        return "HPF"
    if kind in ("BPF", "BANDPASS", "BAND-PASS"):
        return "BPF"
    if kind in ("LPF24", "LOWPASS24", "LOW-PASS24"):
        return "LPF24"
    return DEFAULT_FILTER_TYPE


def filter_type_to_amy_value(value):
    kind = normalize_filter_type(value)
    try:
        import amy
    except Exception:
        return None
    if kind == "HPF":
        return amy.FILTER_HPF
    if kind == "BPF":
        return amy.FILTER_BPF
    if kind == "LPF24":
        if hasattr(amy, "FILTER_LPF24"):
            return amy.FILTER_LPF24
        return amy.FILTER_LPF
    return amy.FILTER_LPF


# -----------------------------
# Display
# -----------------------------
class Display:
    def __init__(self, rotate=90):
        self.kind = "none"
        self.width = 128
        self.height = 128
        self._d = None

        # Try SH1107 direct driver first (rotation support)
        try:
            import sh1107

            i2c = amyboard.get_i2c()
            self._d = sh1107.SH1107_I2C(
                128, 128, i2c, address=0x3C, rotate=rotate
            )
            self.kind = "sh1107"
            return
        except Exception:
            pass

        # Fallback to amyboard display
        try:
            amyboard.init_display()
            self._d = amyboard.display
            self.kind = "amyboard"
            return
        except Exception:
            self.kind = "none"

    def clear(self):
        if self.kind == "none":
            return
        self._d.fill(0)

    def text(self, msg, x, y, color=255):
        if self.kind == "none":
            return
        s = str(msg)
        if self.kind == "sh1107":
            self._d.text(s, x, y, 1 if color else 0)
        else:
            self._d.text(s, x, y, color)

    def fill_rect(self, x, y, w, h, color):
        if self.kind == "none":
            return
        if self.kind == "sh1107":
            self._d.fill_rect(x, y, w, h, 1 if color else 0)
        else:
            self._d.fill_rect(x, y, w, h, color)

    def rect(self, x, y, w, h, color):
        if self.kind == "none":
            return
        if self.kind == "sh1107":
            self._d.rect(x, y, w, h, 1 if color else 0)
        else:
            self._d.rect(x, y, w, h, color)

    def refresh(self):
        if self.kind == "none":
            return
        if self.kind == "sh1107":
            self._d.show()
        else:
            amyboard.display_refresh()

    def bar(self, x, y, w, h, value, max_value=127):
        self.rect(x, y, w, h, 255)
        fill_w = int((clamp(value, 0, max_value) / float(max_value)) * (w - 2))
        if fill_w > 0:
            self.fill_rect(x + 1, y + 1, fill_w, h - 2, 255)

    def line(self, x0, y0, x1, y1, color=255):
        if self.kind == "none":
            return
        c = 1 if self.kind == "sh1107" and color else (color if self.kind != "sh1107" else 0)
        try:
            self._d.line(int(x0), int(y0), int(x1), int(y1), c)
        except Exception:
            pass

    def pixel(self, x, y, color=255):
        if self.kind == "none":
            return
        c = 1 if self.kind == "sh1107" and color else (color if self.kind != "sh1107" else 0)
        try:
            self._d.pixel(int(x), int(y), c)
        except Exception:
            pass

    def hline(self, x, y, w, color=255):
        if self.kind == "none":
            return
        c = 1 if self.kind == "sh1107" and color else (color if self.kind != "sh1107" else 0)
        try:
            self._d.hline(int(x), int(y), int(w), c)
        except Exception:
            pass

    def vline(self, x, y, h, color=255):
        if self.kind == "none":
            return
        c = 1 if self.kind == "sh1107" and color else (color if self.kind != "sh1107" else 0)
        try:
            self._d.vline(int(x), int(y), int(h), c)
        except Exception:
            pass


# -----------------------------
# Input events + drivers
# -----------------------------
class InputEvent:
    def __init__(self, delta=0, click=False, long_press=False, pressed=False):
        self.delta = delta
        self.click = click
        self.long_press = long_press
        self.pressed = pressed


class BaseInputDriver:
    name = "base"

    def poll(self, now_ms):
        return InputEvent()


class DemoInputDriver(BaseInputDriver):
    name = "demo"

    def __init__(self, step_ms=900):
        self.step_ms = step_ms
        self.last_ms = 0
        # Small repeating script to prove menu flow
        self.script = [
            ("delta", 1),
            ("delta", 1),
            ("click", True),
            ("delta", 1),
            ("delta", 1),
            ("click", True),
            ("delta", -1),
            ("long", True),
        ]
        self.idx = 0

    def poll(self, now_ms):
        if now_ms - self.last_ms < self.step_ms:
            return InputEvent()
        self.last_ms = now_ms
        kind, val = self.script[self.idx]
        self.idx = (self.idx + 1) % len(self.script)
        if kind == "delta":
            return InputEvent(delta=val)
        if kind == "click":
            return InputEvent(click=val)
        if kind == "long":
            return InputEvent(long_press=val)
        return InputEvent()

class ComputerInputDriver(BaseInputDriver):
    name = "computer"

    def __init__(self):
        self.queue = []
        self.enabled = False
        self.stdin = None
        self.poller = None

        try:
            import sys
            try:
                import uselect as select
            except Exception:
                import select
            self.stdin = sys.stdin
            self.poller = select.poll()
            self.poller.register(self.stdin, getattr(select, "POLLIN", 1))
            self.enabled = True
        except Exception:
            self.enabled = False

    def _parse_steps(self, parts, default=1):
        if len(parts) < 2:
            return default
        try:
            n = int(parts[1])
            if n < 1:
                return 1
            return n
        except Exception:
            return default

    def _parse_line(self, line):
        s = str(line).strip().lower()
        if not s:
            return []

        parts = s.split()
        cmd = parts[0]

        if cmd in ("up", "u", "k", "prev", "left"):
            return [InputEvent(delta=-self._parse_steps(parts, 1))]
        if cmd in ("down", "d", "j", "next", "right"):
            return [InputEvent(delta=self._parse_steps(parts, 1))]
        if cmd == "delta":
            if len(parts) < 2:
                return []
            try:
                n = int(parts[1])
            except Exception:
                return []
            if n == 0:
                return []
            return [InputEvent(delta=n)]
        if cmd in ("click", "select", "enter", "ok"):
            return [InputEvent(click=True)]
        if cmd in ("back", "long", "hold", "panic", "esc"):
            return [InputEvent(long_press=True)]
        return []

    def poll(self, now_ms):
        if self.queue:
            return self.queue.pop(0)
        if not self.enabled:
            return InputEvent()

        try:
            ready = self.poller.poll(0)
        except Exception:
            ready = []
        if not ready:
            return InputEvent()

        try:
            line = self.stdin.readline()
        except Exception:
            return InputEvent()
        if not line:
            return InputEvent()

        self.queue.extend(self._parse_line(line))
        if self.queue:
            return self.queue.pop(0)
        return InputEvent()


class MIDIInputDriver(BaseInputDriver):
    name = "midi"
    MAX_QUEUE = 48

    def __init__(self, channel_getter=None):
        self.channel_getter = channel_getter or (lambda: 1)
        self.queue = []
        self.running_status = None
        self.data = bytearray()
        self.enabled = False
        self.uart = None
        self.backend = "none"
        self._init_uart()

    def _init_uart(self):
        try:
            import machine

            kwargs = {"baudrate": MIDI_BAUD}
            if MIDI_RX_PIN is not None:
                kwargs["rx"] = machine.Pin(MIDI_RX_PIN)
            if MIDI_TX_PIN is not None:
                kwargs["tx"] = machine.Pin(MIDI_TX_PIN)
            self.uart = machine.UART(MIDI_UART_ID, **kwargs)
            self.enabled = True
            self.backend = "uart%d" % MIDI_UART_ID
            self.name = "midi:" + self.backend
        except Exception:
            self.enabled = False
            self.uart = None

    def _msg_len(self, status):
        hi = status & 0xF0
        if hi in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
            return 2
        if hi in (0xC0, 0xD0):
            return 1
        return 0

    def _target_channel(self):
        try:
            return clamp(int(self.channel_getter()), 1, 16)
        except Exception:
            return 1

    def _channel_match(self, status):
        return ((status & 0x0F) + 1) == self._target_channel()

    def _cc_to_delta(self, value):
        if value == 0 or value == 64:
            return 0
        if value == 1:
            return 1
        if value == 127:
            return -1
        if value < 64:
            return 1
        return -1

    def _emit_for_message(self, status, d1, d2):
        if not self._channel_match(status):
            return
        def push(ev):
            if len(self.queue) < self.MAX_QUEUE:
                self.queue.append(ev)

        typ = status & 0xF0
        if typ == 0x90 and d2 > 0:
            if d1 == MIDI_NOTE_UP:
                push(InputEvent(delta=-1))
            elif d1 == MIDI_NOTE_DOWN:
                push(InputEvent(delta=1))
            elif d1 == MIDI_NOTE_SELECT:
                push(InputEvent(click=True))
            elif d1 == MIDI_NOTE_BACK:
                push(InputEvent(long_press=True))
        elif typ == 0xB0:
            if d1 == MIDI_NAV_CC:
                delta = self._cc_to_delta(d2)
                if delta:
                    push(InputEvent(delta=delta))
            elif d1 == MIDI_SELECT_CC and d2 > 0:
                push(InputEvent(click=True))
            elif d1 == MIDI_BACK_CC and d2 > 0:
                push(InputEvent(long_press=True))

    def _feed_byte(self, b):
        if b & 0x80:
            if b >= 0xF8:  # real-time messages
                return
            if b >= 0xF0:
                self.running_status = None
                self.data = bytearray()
                return
            self.running_status = b
            self.data = bytearray()
            return

        if self.running_status is None:
            return

        need = self._msg_len(self.running_status)
        if need <= 0:
            self.data = bytearray()
            return

        self.data.append(b)
        while len(self.data) >= need:
            if need == 1:
                d1 = self.data[0]
                d2 = 0
                self.data = self.data[1:]
            else:
                d1 = self.data[0]
                d2 = self.data[1]
                self.data = self.data[2:]
            self._emit_for_message(self.running_status, d1, d2)

    def poll(self, now_ms):
        if self.queue:
            return self.queue.pop(0)
        if not self.enabled or self.uart is None:
            return InputEvent()

        try:
            raw = self.uart.read()
        except Exception:
            raw = None
        if raw:
            if isinstance(raw, int):
                raw = bytes([raw])
            for b in raw:
                self._feed_byte(b)

        if self.queue:
            return self.queue.pop(0)
        return InputEvent()


class CombinedInputDriver(BaseInputDriver):
    name = "combined"

    def __init__(self, drivers, name="combined"):
        self.drivers = [d for d in drivers if d is not None]
        self.name = name

    def poll(self, now_ms):
        out = InputEvent()
        active = False
        for d in self.drivers:
            ev = d.poll(now_ms)
            if ev.delta or ev.click or ev.long_press or ev.pressed:
                active = True
                out.delta += ev.delta
                out.click = out.click or ev.click
                out.long_press = out.long_press or ev.long_press
                out.pressed = out.pressed or ev.pressed
        if active:
            return out
        return InputEvent()


class AdafruitEncoderInputDriver(BaseInputDriver):
    name = "adafruit"
    SEESAW_ADDR_CANDIDATES = (0x36, 0x37, 0x49)
    SS_GPIO_BASE = 0x01
    SS_GPIO_DIRCLR_BULK = 0x03
    SS_GPIO_BULK_SET = 0x05
    SS_GPIO_PULLENSET = 0x0B
    SS_GPIO_BULK = 0x04
    SS_ENCODER_BASE = 0x11
    SS_ENCODER_POSITION = 0x30
    SS_BUTTON_PIN = 24

    def __init__(self, encoder_index=0, long_press_ms=650):
        self.encoder_index = encoder_index
        self.long_press_ms = long_press_ms

        self.last_pos = 0
        self.prev_pressed = False
        self.press_start = 0
        self.i2c = amyboard.get_i2c()
        self.seesaw_addr = None
        self.button_mask = 1 << self.SS_BUTTON_PIN

        try:
            devs = self.i2c.scan()
        except Exception:
            devs = []
        for addr in self.SEESAW_ADDR_CANDIDATES:
            if addr in devs:
                self.seesaw_addr = addr
                break

        if self.seesaw_addr is not None:
            try:
                # Configure seesaw button GPIO as input pull-up.
                self._ss_write_u32(self.SS_GPIO_DIRCLR_BULK, self.button_mask)
                self._ss_write_u32(self.SS_GPIO_PULLENSET, self.button_mask)
                self._ss_write_u32(self.SS_GPIO_BULK_SET, self.button_mask)
            except Exception:
                pass
            try:
                self.last_pos = self._ss_read_pos()
            except Exception:
                self.last_pos = 0
            return

        try:
            self.last_pos = amyboard.read_encoder(encoder=self.encoder_index)
        except Exception:
            self.last_pos = 0
        try:
            amyboard.init_buttons()
        except Exception:
            pass

    def _ss_write_u32(self, reg, value):
        self.i2c.writeto(
            self.seesaw_addr,
            bytes([self.SS_GPIO_BASE, reg]) + int(value).to_bytes(4, "big"),
        )

    def _ss_read(self, base, reg, n):
        self.i2c.writeto(self.seesaw_addr, bytes([base, reg]))
        time.sleep_us(80)
        return self.i2c.readfrom(self.seesaw_addr, n)

    def _ss_read_pos(self):
        raw = self._ss_read(self.SS_ENCODER_BASE, self.SS_ENCODER_POSITION, 4)
        return int.from_bytes(raw, "big", True)

    def _get_pressed(self):
        if self.seesaw_addr is not None:
            try:
                bulk = int.from_bytes(self._ss_read(self.SS_GPIO_BASE, self.SS_GPIO_BULK, 4), "big")
                # Input pull-up: LOW means pressed.
                return (bulk & self.button_mask) == 0
            except Exception:
                return False
        try:
            b = amyboard.read_buttons()
            if isinstance(b, (tuple, list)) and len(b) > self.encoder_index:
                return bool(b[self.encoder_index])
        except Exception:
            pass
        return False

    def poll(self, now_ms):
        delta = 0
        click = False
        long_press = False

        try:
            if self.seesaw_addr is not None:
                p = self._ss_read_pos()
            else:
                p = amyboard.read_encoder(encoder=self.encoder_index)
            delta = p - self.last_pos
            self.last_pos = p
        except Exception:
            pass

        pressed = self._get_pressed()
        if pressed and not self.prev_pressed:
            self.press_start = now_ms
        elif (not pressed) and self.prev_pressed:
            dur = now_ms - self.press_start
            if dur >= self.long_press_ms:
                long_press = True
            else:
                click = True

        self.prev_pressed = pressed
        return InputEvent(delta=delta, click=click, long_press=long_press, pressed=pressed)


class TwistInputDriver(BaseInputDriver):
    name = "twist"

    REG_STATUS = 0x01
    REG_COUNT = 0x05

    def __init__(self, long_press_ms=650):
        self.long_press_ms = long_press_ms
        self.i2c = amyboard.get_i2c()
        self.addr = None
        self.prev_pressed = False
        self.press_start = 0
        self.last_count = 0

        devs = self.i2c.scan()
        if 0x3F in devs:
            self.addr = 0x3F
        elif 0x3E in devs:
            self.addr = 0x3E

        if self.addr is not None:
            self.last_count = self._read_i16(self.REG_COUNT)

    def _read_u8(self, reg):
        b = self.i2c.readfrom_mem(self.addr, reg, 1)
        return b[0]

    def _read_i16(self, reg):
        b = self.i2c.readfrom_mem(self.addr, reg, 2)  # little-endian
        v = b[0] | (b[1] << 8)
        if v & 0x8000:
            v -= 65536
        return v

    def poll(self, now_ms):
        if self.addr is None:
            return InputEvent()

        delta = 0
        click = False
        long_press = False
        pressed = False

        try:
            c = self._read_i16(self.REG_COUNT)
            delta = c - self.last_count
            self.last_count = c

            status = self._read_u8(self.REG_STATUS)
            pressed = (status & 0x02) != 0
            click = (status & 0x04) != 0
            self.i2c.writeto_mem(self.addr, self.REG_STATUS, b"\x00")
        except Exception:
            return InputEvent()

        if pressed and not self.prev_pressed:
            self.press_start = now_ms
        elif (not pressed) and self.prev_pressed:
            dur = now_ms - self.press_start
            if dur >= self.long_press_ms:
                long_press = True

        self.prev_pressed = pressed
        return InputEvent(delta=delta, click=click, long_press=long_press, pressed=pressed)


def make_input_driver(mode, midi_channel_getter=None):
    mode = (mode or "").lower()
    if mode == "demo":
        return DemoInputDriver()
    if mode == "computer":
        return ComputerInputDriver()
    if mode == "midi":
        return MIDIInputDriver(channel_getter=midi_channel_getter)
    if mode == "hybrid":
        return CombinedInputDriver(
            [
                ComputerInputDriver(),
                MIDIInputDriver(channel_getter=midi_channel_getter),
            ],
            name="hybrid",
        )
    if mode == "adafruit":
        return AdafruitEncoderInputDriver()
    if mode == "twist":
        return TwistInputDriver()
    # auto
    t = TwistInputDriver()
    if t.addr is not None:
        return t
    return AdafruitEncoderInputDriver()


# -----------------------------
# Pages
# -----------------------------
class PageBase:
    title = "Page"

    def __init__(self, app):
        self.app = app
        self.sel = 0
        self.editing = False

    def on_enter(self):
        pass

    def on_event(self, ev):
        pass

    def render(self, d):
        d.text(self.title, 0, 0, 255)


class GroupPage(PageBase):
    def __init__(self, app, title, items, page_keys):
        super().__init__(app)
        self.title = title
        self.items = ["< Back"] + items
        self.page_keys = ["__back__"] + page_keys
        self.offset = 0

    def on_enter(self):
        self.sel = 1 if len(self.items) > 1 else 0
        self.offset = 0

    def on_event(self, ev):
        if ev.long_press:
            self.app.back_to_menu()
            return
        if ev.delta != 0:
            self.sel = (self.sel + ev.delta) % len(self.items)
            if self.sel < self.offset:
                self.offset = self.sel
            elif self.sel >= self.offset + 6:
                self.offset = self.sel - 5
        if ev.click:
            key = self.page_keys[self.sel]
            if key == "__back__":
                self.app.back_to_menu()
            else:
                self.app.open_page(key)

    def render(self, d):
        d.text(self.title, 0, 1, 255)
        d.hline(0, 12, 128, 255)
        visible_count = 6
        start = self.offset
        end = min(len(self.items), start + visible_count)
        y = 18
        for i in range(start, end):
            marker = ">" if i == self.sel else " "
            d.text("%s %s" % (marker, self.items[i][:13]), 0, y, 255)
            y += 16

        if len(self.items) > visible_count:
            track_h = 96
            thumb_h = max(12, int((visible_count / len(self.items)) * track_h))
            thumb_y = 18 + int((self.sel / (len(self.items) - 1)) * (track_h - thumb_h))
            d.vline(126, 18, track_h, 255)
            d.fill_rect(125, thumb_y, 3, thumb_h, 255)


class PerformPage(PageBase):
    title = "Performance"

    def on_event(self, ev):
        if ev.long_press:
            self.app.back_to_menu()
            return
        if ev.click:
            seq = self.app.cfg.setdefault("sequencer", {})
            seq["running"] = not seq.get("running", False)
            if not seq["running"]:
                self.app.sequencer_stop()
        if ev.delta != 0:
            p = self.app._preset_values()
            p["patch"] = clamp(p["patch"] + ev.delta, BUILTIN_PATCH_MIN, BUILTIN_PATCH_MAX)
            try:
                import amy
                amy.send(synth=p["synth"], patch=p["patch"], note=60, vel=0.75)
                self.app.audition_off_time = time.ticks_add(time.ticks_ms(), 120)
            except Exception:
                pass

    def render(self, d):
        p = self.app._preset_values()
        seq = self.app.cfg.setdefault("sequencer", {})
        macros = self.app.cfg.setdefault("macros", {}).get("values", [64, 64, 64, 64])
        pname = self.app.patch_label(p["patch"])

        # 1. Top Ribbon: Patch & Transport State (y=0..12)
        status_str = "RUN" if seq.get("running", False) else "STP"
        d.text("[%s] #%03d" % (status_str, p["patch"]), 0, 1, 255)
        d.text(pname[:6], 80, 1, 255)
        d.hline(0, 12, 128, 255)

        # 2. Left Macro Meters: M1 & M2 (x=0..12, y=16..84)
        for idx, mx in enumerate([0, 7]):
            val = macros[idx]
            norm = clamp(val / 127.0, 0.0, 1.0)
            bh = int(norm * 64)
            d.rect(mx, 16, 5, 68, 255)
            if bh > 0:
                d.fill_rect(mx, 84 - bh, 5, bh, 255)

        # 3. Right Macro Meters: M3 & M4 (x=115..127, y=16..84)
        for idx, mx in enumerate([115, 122]):
            val = macros[idx + 2]
            norm = clamp(val / 127.0, 0.0, 1.0)
            bh = int(norm * 64)
            d.rect(mx, 16, 5, 68, 255)
            if bh > 0:
                d.fill_rect(mx, 84 - bh, 5, bh, 255)

        # 4. Center Audio Scope (x=16..112, y=16..84)
        d.rect(15, 16, 97, 68, 255)
        for x in range(17, 110, 4):
            d.pixel(x, 50, 255)

        try:
            import struct, amy
            buf = amy.get_output_buffer()
            if buf:
                all_s = struct.unpack("<512h", buf)
                stride = 8
                pts = [all_s[i] / 32768.0 for i in range(0, min(len(all_s), 48 * stride * 2), 2 * stride)]
                y_prev = 50
                for i in range(min(48, len(pts))):
                    x0 = 17 + i * 2
                    y_curr = clamp(int(50 - pts[i] * 28), 18, 82)
                    if i > 0:
                        d.line(x0 - 2, y_prev, x0, y_curr, 255)
                    y_prev = y_curr
        except Exception:
            pass

        # 5. Bottom Ribbon: Sequencer Step Track (y=88..127)
        d.hline(0, 88, 128, 255)
        bpm = seq.get("bpm", 120)
        d.text("BPM:%s" % ("EXT" if bpm == 0 else "%d" % bpm), 0, 92, 255)
        if self.app.seq_last_note >= 0:
            n_name = SequencerPage.NOTE_NAMES[self.app.seq_last_note % 12]
            n_oct = (self.app.seq_last_note // 12) - 1
            d.text("N:%s%d" % (n_name, n_oct), 72, 92, 255)
        else:
            d.text("Vox:%d" % p.get("num_voices", 1), 76, 92, 255)

        curr_step = self.app.seq_step % 16 if seq.get("running", False) else -1
        for i in range(16):
            sx = 4 + i * 7
            sy = 108
            d.rect(sx, sy, 5, 5, 255)
            if i == curr_step:
                d.fill_rect(sx, sy, 5, 5, 255)


class DrumMachinePage(PageBase):
    title = "Drums"
    TRACK_NAMES = ["KICK", "SNARE", "HIHAT", "PERC"]
    FIELDS = ["STATE", "TRACK", "HITS", "ROTATE", "MUTE", "VOL", "BPM"]

    def __init__(self, app):
        super().__init__(app)
        self.track_idx = 0
        self.sel = 0
        self.editing = False

    def on_enter(self):
        self.editing = False

    def on_event(self, ev):
        if ev.long_press:
            self.app.back_to_menu()
            return
        
        drums = self.app.cfg.setdefault("drums", {
            "running": False,
            "bpm": 120,
            "tracks": [
                {"hits": 4, "steps": 16, "rotate": 0, "mute": False, "vol": 90},
                {"hits": 2, "steps": 16, "rotate": 4, "mute": False, "vol": 85},
                {"hits": 8, "steps": 16, "rotate": 0, "mute": False, "vol": 70},
                {"hits": 3, "steps": 12, "rotate": 2, "mute": False, "vol": 75},
            ]
        })
        t = drums["tracks"][self.track_idx]

        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.FIELDS)
            if ev.click:
                f = self.FIELDS[self.sel]
                if f == "STATE":
                    drums["running"] = not drums.get("running", False)
                elif f == "MUTE":
                    t["mute"] = not t.get("mute", False)
                else:
                    self.editing = True
            return

        f = self.FIELDS[self.sel]
        if ev.delta != 0:
            if f == "STATE":
                drums["running"] = not drums.get("running", False)
            elif f == "TRACK":
                self.track_idx = (self.track_idx + ev.delta) % 4
            elif f == "HITS":
                t["hits"] = clamp(t.get("hits", 4) + ev.delta, 0, t.get("steps", 16))
            elif f == "ROTATE":
                t["rotate"] = (t.get("rotate", 0) + ev.delta) % t.get("steps", 16)
            elif f == "MUTE":
                t["mute"] = not t.get("mute", False)
            elif f == "VOL":
                t["vol"] = clamp(t.get("vol", 80) + ev.delta * 5, 0, 100)
            elif f == "BPM":
                drums["bpm"] = clamp(drums.get("bpm", 120) + ev.delta * 2, 40, 240)

        if ev.click:
            self.editing = False
            self.app.save_state()

    def render(self, d):
        drums = self.app.cfg.setdefault("drums", {
            "running": False, "bpm": 120,
            "tracks": [
                {"hits": 4, "steps": 16, "rotate": 0, "mute": False, "vol": 90},
                {"hits": 2, "steps": 16, "rotate": 4, "mute": False, "vol": 85},
                {"hits": 8, "steps": 16, "rotate": 0, "mute": False, "vol": 70},
                {"hits": 3, "steps": 12, "rotate": 2, "mute": False, "vol": 75},
            ]
        })
        running = drums.get("running", False)
        bpm = drums.get("bpm", 120)

        # 1. Header (y=0..12)
        d.text("DRUMS %s" % ("[RUN]" if running else "[STP]"), 0, 1, 255)
        d.text("%dBPM" % bpm, 76, 1, 255)
        d.hline(0, 12, 128, 255)

        # 2. 4 Track Matrix Rows (y=16..68)
        curr_step = self.app.drum_step if running else -1
        for tidx in range(4):
            t = drums["tracks"][tidx]
            ty = 16 + tidx * 13
            is_cur = (tidx == self.track_idx)
            marker = ">" if is_cur else " "
            name_short = self.TRACK_NAMES[tidx][:2]
            mute_str = "M" if t.get("mute", False) else " "
            d.text("%s%s%s" % (marker, name_short, mute_str), 0, ty, 255)

            hits = t.get("hits", 4)
            steps = t.get("steps", 16)
            rot = t.get("rotate", 0)
            raw = generate_euclidean(hits, steps)
            euc = [raw[(i - rot) % steps] for i in range(steps)]

            for step_i in range(steps):
                px = 30 + step_i * 6
                d.rect(px, ty + 1, 5, 6, 255)
                if euc[step_i]:
                    d.fill_rect(px + 1, ty + 2, 3, 4, 255)
                if (curr_step % steps) == step_i and running:
                    d.vline(px + 2, ty, 8, 255)

        d.hline(0, 72, 128, 255)

        # 3. Selected Track Parameter Editor (y=76..127)
        t = drums["tracks"][self.track_idx]
        tname = self.TRACK_NAMES[self.track_idx]
        params = [
            ("Play", "RUN" if running else "STOP"),
            ("Track", tname),
            ("Hits", "%d/%d" % (t.get("hits", 4), t.get("steps", 16))),
            ("Rotate", "%d" % t.get("rotate", 0)),
            ("Mute", "YES" if t.get("mute", False) else "NO"),
            ("Volume", "%d%%" % t.get("vol", 80)),
            ("Tempo", "%dBPM" % bpm),
        ]
        
        visible_count = 3
        offset = clamp(self.sel - 1, 0, max(0, len(params) - visible_count))
        y = 78
        for i in range(offset, min(len(params), offset + visible_count)):
            pname, pval = params[i]
            is_sel = (i == self.sel)
            marker = ">" if is_sel else " "
            star = "*" if (is_sel and self.editing) else " "
            d.text("%s%s%s" % (marker, star, pname[:6]), 0, y, 255)
            d.text(pval[:6], 60, y, 255)
            y += 16


class EnvPage(PageBase):
    title = "ADSR Envelope"
    FIELDS = ["TARGET", "ATTACK", "DECAY", "SUSTAIN", "RELEASE"]

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0
        self.editing = False

    def _env(self):
        return self.app.cfg.setdefault("envelope", {
            "target": "AMP",
            "attack": 15,
            "decay": 250,
            "sustain": 70,
            "release": 450,
        })

    def on_event(self, ev):
        if ev.long_press:
            self.app.back_to_menu()
            return
        env = self._env()
        if ev.click:
            self.editing = not self.editing
            if not self.editing:
                self.app.apply_envelope()
                self.app.save_state()
            return
        if ev.delta != 0:
            if not self.editing:
                self.sel = (self.sel + ev.delta) % len(self.FIELDS)
            else:
                f = self.FIELDS[self.sel]
                if f == "TARGET":
                    env["target"] = "FILT" if env.get("target", "AMP") == "AMP" else "AMP"
                elif f == "ATTACK":
                    step = 50 if env["attack"] >= 500 else (10 if env["attack"] >= 100 else 2)
                    env["attack"] = clamp(env["attack"] + ev.delta * step, 1, 4000)
                elif f == "DECAY":
                    step = 50 if env["decay"] >= 500 else 20
                    env["decay"] = clamp(env["decay"] + ev.delta * step, 10, 4000)
                elif f == "SUSTAIN":
                    env["sustain"] = clamp(env["sustain"] + ev.delta * 5, 0, 100)
                elif f == "RELEASE":
                    step = 50 if env["release"] >= 500 else 25
                    env["release"] = clamp(env["release"] + ev.delta * step, 10, 6000)
                self.app.apply_envelope()

    def render(self, d):
        env = self._env()
        d.text("ADSR ENVELOPE", 0, 1, 255)
        mode_str = "EDIT" if self.editing else "SEL"
        d.text("[%s]" % mode_str, 88, 1, 255)
        d.hline(0, 12, 128, 255)

        # 1. Interactive Visual ADSR Envelope Plot (x=4..123, y=16..72)
        d.rect(2, 16, 124, 56, 255)
        d.pixel(2, 71, 255)

        att = env.get("attack", 15)
        dec = env.get("decay", 250)
        sus = env.get("sustain", 70) / 100.0
        rel = env.get("release", 450)

        w_att = clamp(int(10 + (att / 2000.0) * 35), 6, 40)
        w_dec = clamp(int(10 + (dec / 2000.0) * 30), 6, 35)
        w_sus = 25
        w_rel = clamp(int(10 + (rel / 3000.0) * 40), 6, 40)
        total_w = w_att + w_dec + w_sus + w_rel
        scale_f = 116.0 / total_w if total_w > 0 else 1.0

        p0 = (4, 70)
        p1 = (int(4 + w_att * scale_f), 20)
        p2 = (int(p1[0] + w_dec * scale_f), int(70 - sus * 50))
        p3 = (int(p2[0] + w_sus * scale_f), p2[1])
        p4 = (min(122, int(p3[0] + w_rel * scale_f)), 70)

        d.line(p0[0], p0[1], p1[0], p1[1], 255)
        d.line(p1[0], p1[1], p2[0], p2[1], 255)
        d.line(p2[0], p2[1], p3[0], p3[1], 255)
        d.line(p3[0], p3[1], p4[0], p4[1], 255)

        d.pixel(p1[0], p1[1], 255)
        d.pixel(p2[0], p2[1], 255)
        d.pixel(p3[0], p3[1], 255)

        # 2. Parameters List (y=76..127)
        d.hline(0, 74, 128, 255)
        
        # Dense Row 1: Target, Attack
        is_sel0 = (self.sel == 0)
        is_sel1 = (self.sel == 1)
        d.text("%sTgt:%s" % (">" if is_sel0 else " ", env.get("target", "AMP")), 0, 78, 255)
        d.text("%sAtt:%dms" % (">" if is_sel1 else " ", att), 64, 78, 255)

        # Dense Row 2: Decay, Sustain
        is_sel2 = (self.sel == 2)
        is_sel3 = (self.sel == 3)
        d.text("%sDec:%dms" % (">" if is_sel2 else " ", dec), 0, 94, 255)
        d.text("%sSus:%d%%" % (">" if is_sel3 else " ", int(sus * 100)), 64, 94, 255)

        # Dense Row 3: Release
        is_sel4 = (self.sel == 4)
        d.text("%sRel:%dms" % (">" if is_sel4 else " ", rel), 0, 110, 255)


class LFOPage(PageBase):
    title = "Dual LFOs"
    WAVES = ["Sine", "Triangle", "Saw Up", "Saw Dn", "Square", "Random"]
    DESTS = ["Filter", "CV1 Out", "CV2 Out", "Pitch", "PWM", "None"]
    FIELDS = ["LFO_ID", "WAVE", "RATE", "DEPTH", "DEST"]

    def __init__(self, app):
        super().__init__(app)
        self.lfo_id = 0
        self.sel = 0
        self.editing = False

    def _lfo(self):
        lfos = self.app.cfg.setdefault("lfos", [
            {"wave": "Sine", "rate": 1.0, "depth": 75, "dest": "Filter"},
            {"wave": "Triangle", "rate": 0.5, "depth": 50, "dest": "CV1 Out"},
        ])
        while len(lfos) < 2:
            lfos.append({"wave": "Sine", "rate": 1.0, "depth": 50, "dest": "None"})
        return lfos[self.lfo_id]

    def on_event(self, ev):
        if ev.long_press:
            self.app.back_to_menu()
            return
        lfo = self._lfo()
        if ev.click:
            if self.sel == 0:
                self.lfo_id = 1 - self.lfo_id
            else:
                self.editing = not self.editing
                if not self.editing:
                    self.app.save_state()
            return
        if ev.delta != 0:
            if not self.editing:
                self.sel = (self.sel + ev.delta) % len(self.FIELDS)
            else:
                f = self.FIELDS[self.sel]
                if f == "LFO_ID":
                    self.lfo_id = 1 - self.lfo_id
                elif f == "WAVE":
                    idx = self.WAVES.index(lfo.get("wave", "Sine")) if lfo.get("wave") in self.WAVES else 0
                    idx = (idx + ev.delta) % len(self.WAVES)
                    lfo["wave"] = self.WAVES[idx]
                elif f == "RATE":
                    cur = float(lfo.get("rate", 1.0))
                    step = 0.5 if cur >= 5.0 else (0.1 if cur >= 1.0 else 0.05)
                    lfo["rate"] = clamp(round(cur + ev.delta * step, 2), 0.05, 30.0)
                elif f == "DEPTH":
                    lfo["depth"] = clamp(int(lfo.get("depth", 50)) + ev.delta * 5, 0, 100)
                elif f == "DEST":
                    idx = self.DESTS.index(lfo.get("dest", "None")) if lfo.get("dest") in self.DESTS else 0
                    idx = (idx + ev.delta) % len(self.DESTS)
                    lfo["dest"] = self.DESTS[idx]

    def render(self, d):
        lfo = self._lfo()
        d.text("LFO %d" % (self.lfo_id + 1), 0, 1, 255)
        mode_str = "EDIT" if self.editing else "SEL"
        d.text("[%s]" % mode_str, 88, 1, 255)
        d.hline(0, 12, 128, 255)

        # 1. Live Animated Waveform Display (x=4..123, y=16..64)
        d.rect(2, 16, 124, 48, 255)
        for x in range(4, 122, 6):
            d.pixel(x, 40, 255)

        wave = lfo.get("wave", "Sine")
        rate = float(lfo.get("rate", 1.0))
        depth = int(lfo.get("depth", 50)) / 100.0

        now_s = time.ticks_ms() / 1000.0
        phase = (now_s * rate) % 1.0

        import math
        y_prev = 40
        for x in range(4, 124):
            t = ((x - 4) / 120.0 * 2.0 + phase) % 1.0
            if wave == "Sine":
                val = math.sin(t * 2 * math.pi)
            elif wave == "Triangle":
                val = 4.0 * abs(t - 0.5) - 1.0
            elif wave == "Saw Up":
                val = 2.0 * t - 1.0
            elif wave == "Saw Dn":
                val = 1.0 - 2.0 * t
            elif wave == "Square":
                val = 1.0 if t < 0.5 else -1.0
            else:
                val = math.sin(t * 8.0) * 0.7
            
            y_curr = clamp(int(40 - val * depth * 20), 18, 62)
            if x > 4:
                d.line(x - 1, y_prev, x, y_curr, 255)
            y_prev = y_curr

        # 2. Parameters List (y=68..127)
        d.hline(0, 68, 128, 255)
        params = [
            ("LFO", "LFO %d" % (self.lfo_id + 1)),
            ("Wave", wave[:6]),
            ("Rate", "%.2fHz" % rate),
            ("Depth", "%d%%" % int(depth * 100)),
            ("Dest", lfo.get("dest", "None")[:7]),
        ]
        y = 72
        for i, (label, val) in enumerate(params):
            marker = ">" if i == self.sel else " "
            star = "*" if (self.editing and i == self.sel) else " "
            d.text("%s%s%s" % (marker, star, label), 0, y, 255)
            d.text(val, 52, y, 255)
            y += 11


class PatchesPage(PageBase):
    title = "Patches"
    save_label = "[Save current]"

    def __init__(self, app):
        super().__init__(app)
        self.files = []
        self.offset = 0

    def _item_count(self):
        return 1 + len(self.files)

    def _item_label(self, idx):
        if idx == 0:
            return self.save_label
        return short_name(self.files[idx - 1])

    def refresh(self):
        try:
            amyboard.mount_sd()
        except Exception:
            pass
        self.files = scan_patch_files(["/user", "/sd"])
        max_idx = max(0, self._item_count() - 1)
        self.sel = clamp(self.sel, 0, max_idx)
        self.offset = clamp(self.offset, 0, max_idx)

    def on_enter(self):
        self.refresh()

    def on_event(self, ev):
        count = self._item_count()
        if ev.delta != 0:
            self.sel = clamp(self.sel + ev.delta, 0, max(0, count - 1))
            if self.sel < self.offset:
                self.offset = self.sel
            if self.sel >= self.offset + 6:
                self.offset = self.sel - 5
        if ev.click:
            if self.sel == 0:
                saved = self.app.save_patch_profile()
                if saved is None:
                    self.app.notice("Save failed")
                else:
                    self.refresh()
                    try:
                        self.sel = self.files.index(saved) + 1
                    except Exception:
                        self.sel = 0
                    self.app.notice("Saved " + short_name(saved))
            elif len(self.files) > 0:
                p = self.files[self.sel - 1]
                status = self.app.load_patch_profile(p)
                if status == "loaded":
                    self.app.notice("Loaded " + short_name(p))
                else:
                    self.app.notice("Load failed")
        if ev.long_press:
            self.app.back_to_menu()

    def render(self, d):
        d.text("PATCH PROFILES", 0, 1, 255)
        d.hline(0, 12, 128, 255)

        y = 16
        start = self.offset
        end = min(self._item_count(), start + 6)
        current = str(self.app.cfg.get("patches", {}).get("current", ""))
        for i in range(start, end):
            prefix = ">" if i == self.sel else " "
            name = self._item_label(i)
            if i > 0 and self.files[i - 1] == current:
                name = "*" + name
            d.text("%s%s" % (prefix, name[:14]), 0, y, 255)
            y += 15


class PresetVoicePage(PageBase):
    title = "Preset Voice"
    fields = ["patch", "synth", "voices"]

    def _values(self):
        return self.app.cfg["preset_voice"]

    def on_event(self, ev):
        v = self._values()
        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.fields)
            if ev.click:
                self.editing = True
            if ev.long_press:
                self.app.back_to_menu()
            return

        f = self.fields[self.sel]
        if ev.delta != 0:
            if f == "patch":
                v[f] = clamp(int(v.get(f, BUILTIN_PATCH_MIN)) + ev.delta, BUILTIN_PATCH_MIN, BUILTIN_PATCH_MAX)
                # Quick 120ms audition preview note
                try:
                    import amy
                    s_id = int(v.get("synth", 1))
                    amy.send(synth=s_id, patch=v[f], note=60, vel=0.75)
                    self.app.audition_off_time = time.ticks_add(time.ticks_ms(), 120)
                except Exception:
                    pass
            elif f == "synth":
                v["synth"] = clamp(int(v.get("synth", 1)) + ev.delta, 1, 4)
            elif f == "voices":
                v["num_voices"] = clamp(int(v.get("num_voices", 1)) + ev.delta, 1, 16)

        if ev.click:
            self.editing = False
            self.app.apply_preset_voice(save=True, show_notice=True)
        if ev.long_press:
            self.editing = False
            self.app.back_to_menu()

    def render(self, d):
        v = self._values()
        patch = int(v.get("patch", BUILTIN_PATCH_MIN))
        synth = int(v.get("synth", 1))
        voices = int(v.get("num_voices", 1))

        d.text("PRESET VOICE", 0, 1, 255)
        mode_str = "EDIT" if self.editing else "SEL"
        d.text("[%s]" % mode_str, 88, 1, 255)
        d.hline(0, 12, 128, 255)

        # 1. Active Patch Name Banner (y=16..31)
        pname = self.app.patch_label(patch)
        bank_tag = "JUNO" if patch < 128 else ("DX7" if patch < 256 else "PCM")
        d.rect(0, 16, 128, 16, 255)
        d.text("%s: %s" % (bank_tag, pname[:9]), 4, 20, 255)

        # 2. Parameter fields exactly matching self.fields (sel 0, 1, 2)
        rows = [
            ("Patch", "#%03d" % patch),
            ("Synth", "Eng %d" % synth),
            ("Poly", "%d vox" % voices),
        ]
        y = 38
        for i, (label, val) in enumerate(rows):
            marker = ">" if i == self.sel else " "
            star = "*" if (self.editing and i == self.sel) else " "
            d.text("%s%s%s" % (marker, star, label), 0, y, 255)
            d.text(val, 56, y, 255)
            y += 18

        d.hline(0, 96, 128, 255)
        d.text("CV1:1V/Oct CV2:Gate", 0, 100, 255)
        d.text("MIDI Ch:%d" % self.app.cfg["system"]["midi_channel"], 0, 114, 255)


class FilterTypePage(PageBase):
    title = "Filt Type"

    def _values(self):
        return self.app._preset_values()

    def _selected_index(self):
        cur = normalize_filter_type(self._values().get("filter_type", DEFAULT_FILTER_TYPE))
        try:
            return FILTER_TYPE_OPTIONS.index(cur)
        except Exception:
            return 0

    def on_event(self, ev):
        if ev.delta != 0:
            idx = self._selected_index()
            idx = (idx + ev.delta) % len(FILTER_TYPE_OPTIONS)
            self._values()["filter_type"] = FILTER_TYPE_OPTIONS[idx]
            self.app.apply_filter_type(save=True, show_notice=False)
        if ev.click or ev.long_press:
            self.app.back_to_menu()

    def render(self, d):
        cur = normalize_filter_type(self._values().get("filter_type", DEFAULT_FILTER_TYPE))
        d.text("FILTER TOPOLOGY", 0, 1, 255)
        d.hline(0, 12, 128, 255)

        y = 20
        descriptions = {
            "LPF": "12dB Low-Pass",
            "HPF": "12dB High-Pass",
            "BPF": "12dB Band-Pass",
            "LPF24": "24dB 4-Pole LPF",
        }
        for opt in FILTER_TYPE_OPTIONS:
            marker = ">" if opt == cur else " "
            desc = descriptions.get(opt, "")
            d.text("%s %s" % (marker, opt), 0, y, 255)
            d.text(desc[:12], 44, y, 255)
            y += 22

        d.hline(0, 110, 128, 255)
        d.text("Active: %s" % cur, 0, 114, 255)


class FilterCutoffPage(PageBase):
    title = "Filt Cut"

    def _values(self):
        return self.app._preset_values()

    def on_event(self, ev):
        if ev.delta != 0:
            p = self._values()
            step = 250 if p["filter_cutoff"] >= 2500 else (100 if p["filter_cutoff"] >= 1000 else 40)
            p["filter_cutoff"] = clamp(p["filter_cutoff"] + ev.delta * step, 80, 16000)
            self.app.apply_filter_type(save=True, show_notice=False)
        if ev.click or ev.long_press:
            self.app.back_to_menu()

    def render(self, d):
        p = self._values()
        cutoff = p["filter_cutoff"]
        ftype = normalize_filter_type(p.get("filter_type", DEFAULT_FILTER_TYPE))
        res = float(self.app.cfg.get("fx", {}).get("resonance", 1.0))

        # 1. Header
        d.text("FILTER CUTOFF", 0, 1, 255)
        if cutoff >= 1000:
            d.text("%.2fkHz" % (cutoff / 1000.0), 80, 1, 255)
        else:
            d.text("%dHz" % cutoff, 84, 1, 255)
        d.hline(0, 12, 128, 255)

        # 2. Interactive Graphical Filter Frequency Response Curve (Bode Plot)
        # x=4..123, y=20..84
        d.rect(2, 18, 124, 70, 255)
        # Center grid line
        for x in range(4, 122, 6):
            d.pixel(x, 52, 255)

        import math
        norm_fc = clamp((math.log(cutoff) - math.log(80)) / (math.log(16000) - math.log(80)), 0.0, 1.0)
        fc_px = int(4 + norm_fc * 116)

        # Draw filter curve
        y_prev = 52
        for x in range(4, 124):
            dx = (x - fc_px) / 16.0
            if "LP" in ftype:
                # Low pass shelf roll-off
                gain = 1.0 / math.sqrt(1.0 + max(0.0, dx)**4)
                if abs(dx) < 0.8:
                    gain += (res - 1.0) * 0.3 * (1.0 - abs(dx))
            elif "HP" in ftype:
                # High pass shelf roll-off
                gain = 1.0 / math.sqrt(1.0 + max(0.0, -dx)**4)
                if abs(dx) < 0.8:
                    gain += (res - 1.0) * 0.3 * (1.0 - abs(dx))
            else:  # BPF
                # Band pass peak
                gain = 1.0 / (1.0 + (dx * 1.5)**2)
                gain += (res - 1.0) * 0.4 * max(0.0, 1.0 - abs(dx))

            gain = clamp(gain, 0.0, 1.8)
            y_curr = int(82 - gain * 34)
            y_curr = clamp(y_curr, 20, 84)
            if x > 4:
                d.line(x - 1, y_prev, x, y_curr, 255)
            y_prev = y_curr

        # Vertical cutoff frequency line
        for y in range(20, 84, 3):
            d.pixel(fc_px, y, 255)

        # 3. Footer info
        d.hline(0, 94, 128, 255)
        d.text("Type:%s  Res:%.1f" % (ftype, res), 0, 100, 255)
        d.text("Range: 80Hz - 16kHz", 0, 114, 255)


class VoiceModePage(PageBase):
    title = "Voice Mode"
    fields = ["polyphony", "unison", "detune", "spread"]

    def _values(self):
        return self.app.cfg["voice_mode"]

    def on_event(self, ev):
        v = self._values()
        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.fields)
            if ev.click:
                self.editing = True
            if ev.long_press:
                self.app.back_to_menu()
            return

        f = self.fields[self.sel]
        if ev.delta != 0:
            if f == "polyphony":
                v[f] = clamp(v[f] + ev.delta, 1, 16)
            elif f == "unison":
                v[f] = not v[f]
            elif f == "detune":
                v[f] = clamp(v[f] + ev.delta * 2, 0, 100)
            elif f == "spread":
                v[f] = clamp(v[f] + ev.delta * 2, 0, 100)
        if ev.click:
            self.editing = False
            self.app.save_cfg()
        if ev.long_press:
            self.editing = False
            self.app.back_to_menu()

    def render(self, d):
        d.text("VOICE & UNISON", 0, 1, 255)
        mode_str = "EDIT" if self.editing else "SEL"
        d.text("[%s]" % mode_str, 88, 1, 255)
        d.hline(0, 12, 128, 255)

        v = self._values()
        rows = [
            ("Poly", "%d vox" % v["polyphony"], v["polyphony"], 16),
            ("Unison", "ON" if v["unison"] else "OFF", 1 if v["unison"] else 0, 1),
            ("Detune", "%d%%" % v["detune"], v["detune"], 100),
            ("Spread", "%d%%" % v["spread"], v["spread"], 100),
        ]
        y = 18
        for i, (label, val_str, val_num, val_max) in enumerate(rows):
            marker = ">" if i == self.sel else " "
            star = "*" if (self.editing and i == self.sel) else " "
            d.text("%s%s%s" % (marker, star, label), 0, y, 255)
            d.text(val_str, 60, y, 255)

            # Mini bar
            norm = clamp(val_num / val_max if val_max > 0 else 0, 0.0, 1.0)
            bw = int(norm * 22)
            d.rect(98, y + 1, 24, 7, 255)
            if bw > 0:
                d.fill_rect(98, y + 1, bw, 7, 255)
            y += 20

        d.hline(0, 104, 128, 255)
        d.text("Stereo Engine Ready", 0, 110, 255)


class MacrosPage(PageBase):
    title = "Macros"

    MACRO_NAMES = ["M1 Filter", "M2 Res", "M3 Env", "M4 FX"]

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0

    def on_event(self, ev):
        vals = self.app.cfg["macros"]["values"]
        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % 4
            if ev.click:
                self.editing = True
            if ev.long_press:
                self.app.back_to_menu()
            return

        if ev.delta != 0:
            vals[self.sel] = clamp(vals[self.sel] + ev.delta * 2, 0, 127)
        if ev.click:
            self.editing = False
            self.app.save_cfg()
        if ev.long_press:
            self.editing = False
            self.app.back_to_menu()

    def render(self, d):
        vals = self.app.cfg["macros"]["values"]
        d.text("PERFORMANCE MACROS", 0, 1, 255)
        d.hline(0, 12, 128, 255)

        y = 18
        for i in range(4):
            marker = ">" if i == self.sel else " "
            star = "*" if (self.editing and i == self.sel) else " "
            val = vals[i]
            d.text("%s%s%s" % (marker, star, self.MACRO_NAMES[i][:9]), 0, y, 255)
            d.text("%03d" % val, 82, y, 255)

            # Full-width level bar
            norm = clamp(val / 127.0, 0.0, 1.0)
            bw = int(norm * 116)
            d.rect(6, y + 11, 118, 5, 255)
            if bw > 0:
                d.fill_rect(6, y + 11, bw, 5, 255)
            y += 24


class SystemPage(PageBase):
    title = "System"
    items = ["I2C Scan", "Control", "MIDI Ch", "Input", "Save Cfg", "Reload", "Panic"]

    def __init__(self, app):
        super().__init__(app)
        self.scan_cache = []
        self._control_before_edit = None
        self.offset = 0

    def on_event(self, ev):
        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.items)
            if ev.click:
                item = self.items[self.sel]
                if item == "I2C Scan":
                    try:
                        self.scan_cache = amyboard.get_i2c().scan()
                        self.app.notice("I2C: " + ",".join([hex(x) for x in self.scan_cache]))
                    except Exception:
                        self.app.notice("I2C scan error")
                elif item == "Control":
                    self._control_before_edit = self.app.cfg["system"]["control_source"]
                    self.editing = True
                elif item == "MIDI Ch":
                    self.editing = True
                elif item == "Input":
                    self.app.notice("Input: " + self.app.input_driver.name)
                elif item == "Save Cfg":
                    ok = self.app.save_cfg() and self.app.save_state()
                    self.app.notice("Config Saved" if ok else "Save failed")
                elif item == "Reload":
                    self.app.pages["patches"].refresh()
                    self.app.notice("Patches reloaded")
                elif item == "Panic":
                    self.app.panic()
                    self.app.notice("All Notes OFF")
            if ev.long_press:
                self.app.back_to_menu()
            return

        if self.items[self.sel] == "Control":
            if ev.delta != 0:
                modes = self.app.control_sources
                cur = self.app.cfg["system"]["control_source"]
                idx = modes.index(cur) if cur in modes else 0
                idx = (idx + ev.delta) % len(modes)
                self.app.cfg["system"]["control_source"] = modes[idx]
            if ev.click:
                self.editing = False
                self.app.apply_control_source(
                    self.app.cfg["system"]["control_source"], save=True, show_notice=True
                )
            if ev.long_press:
                if self._control_before_edit is not None:
                    self.app.cfg["system"]["control_source"] = self._control_before_edit
                self.editing = False
                self.app.back_to_menu()
            return

        if self.items[self.sel] == "MIDI Ch":
            if ev.delta != 0:
                ch = self.app.cfg["system"]["midi_channel"]
                self.app.cfg["system"]["midi_channel"] = clamp(ch + ev.delta, 1, 16)
            if ev.click:
                self.editing = False
                self.app.save_cfg()
            if ev.long_press:
                self.editing = False
                self.app.back_to_menu()

    def render(self, d):
        d.text("SYSTEM & DIAG", 0, 1, 255)
        d.hline(0, 12, 128, 255)

        visible_count = 6
        if self.sel < self.offset:
            self.offset = self.sel
        elif self.sel >= self.offset + visible_count:
            self.offset = self.sel - visible_count + 1

        y = 18
        start = self.offset
        end = min(len(self.items), start + visible_count)
        for i in range(start, end):
            it = self.items[i]
            marker = ">" if i == self.sel else " "
            star = "*" if (self.editing and i == self.sel) else " "
            line = it
            if it == "Control":
                line = "Ctrl:%s" % self.app.cfg["system"]["control_source"]
            elif it == "MIDI Ch":
                line = "MIDI Ch:%d" % self.app.cfg["system"]["midi_channel"]
            elif it == "Input":
                line = "In:%s" % self.app.input_driver.name[:8]
            d.text("%s%s%s" % (marker, star, line[:15]), 0, y, 255)
            y += 16


class CVRoutingPage(PageBase):
    title = "CV Routing"

    IN_TARGETS = [
        "none",
        "pitch",
        "filter",
        "amp",
        "reverb",
        "chorus",
        "echo",
        "macro1",
        "macro2",
        "macro3",
        "macro4",
    ]
    OUT1_TARGETS = ["pitch", "sequencer", "lfo1", "envelope", "none"]
    OUT2_TARGETS = ["gate", "seq_clock", "velocity", "lfo2", "none"]

    CHANNELS = ["CV1 IN", "CV2 IN", "CV1 OUT", "CV2 OUT"]
    fields = ["channel", "target", "amount", "polarity", "smooth"]

    def __init__(self, app):
        super().__init__(app)
        self.ch_idx = 0

    def _route(self):
        routes = self.app.cfg["cv_routing"].setdefault("routes", [
            {"target": "none", "amount": 0, "polarity": 1, "smooth": 20},
            {"target": "none", "amount": 0, "polarity": 1, "smooth": 20},
            {"target": "pitch", "amount": 100, "polarity": 1, "smooth": 0},
            {"target": "gate", "amount": 100, "polarity": 1, "smooth": 0},
        ])
        while len(routes) < 4:
            routes.append({"target": "none", "amount": 0, "polarity": 1, "smooth": 0})
        return routes[self.ch_idx]

    def on_event(self, ev):
        r = self._route()

        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.fields)
            if ev.click:
                self.editing = True
            if ev.long_press:
                self.app.back_to_menu()
            return

        f = self.fields[self.sel]
        if ev.delta != 0:
            if f == "channel":
                self.ch_idx = (self.ch_idx + ev.delta) % len(self.CHANNELS)
            elif f == "target":
                if self.ch_idx < 2:
                    t_list = self.IN_TARGETS
                elif self.ch_idx == 2:
                    t_list = self.OUT1_TARGETS
                else:
                    t_list = self.OUT2_TARGETS
                idx = t_list.index(r["target"]) if r["target"] in t_list else 0
                idx = (idx + ev.delta) % len(t_list)
                r["target"] = t_list[idx]
            elif f == "amount":
                r["amount"] = clamp(r["amount"] + ev.delta * 5, -100, 100)
            elif f == "polarity":
                r["polarity"] = -1 if r["polarity"] > 0 else 1
            elif f == "smooth":
                r["smooth"] = clamp(r["smooth"] + ev.delta * 5, 0, 100)

        if ev.click:
            self.editing = False
            self.app.save_cfg()
        if ev.long_press:
            self.editing = False
            self.app.back_to_menu()

    def render(self, d):
        r = self._route()
        ch_name = self.CHANNELS[self.ch_idx]
        d.text("CV ROUTING", 0, 1, 255)
        d.hline(0, 12, 128, 255)

        rows = [
            ("Chan", ch_name),
            ("Target", r["target"][:9]),
            ("Amount", "%d%%" % r["amount"]),
            ("Polar", "+" if r["polarity"] > 0 else "-"),
            ("Smooth", "%d" % r["smooth"]),
        ]
        y = 16
        for i, (label, val) in enumerate(rows):
            marker = ">" if i == self.sel else " "
            star = "*" if self.editing and i == self.sel else " "
            d.text("%s%s%s" % (marker, star, label), 0, y, 255)
            d.text(val, 64, y, 255)
            y += 16

        d.hline(0, 104, 128, 255)
        is_out = "OUT" in ch_name
        d.text("Mode: %s" % ("Eurorack OUT" if is_out else "Mod IN"), 0, 108, 255)


class MacrosPage(PageBase):
    title = "Macros"

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0

    def on_event(self, ev):
        vals = self.app.cfg["macros"]["values"]
        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % 4
            if ev.click:
                self.editing = True
            if ev.long_press:
                self.app.back_to_menu()
            return

        if ev.delta != 0:
            vals[self.sel] = clamp(vals[self.sel] + ev.delta, 0, 127)
        if ev.click:
            self.editing = False
            self.app.save_cfg()
        if ev.long_press:
            self.editing = False
            self.app.back_to_menu()

    def render(self, d):
        vals = self.app.cfg["macros"]["values"]
        d.text("Macros", 0, 0, 255)
        y = 14
        for i in range(4):
            marker = ">" if i == self.sel else " "
            star = "*" if self.editing and i == self.sel else " "
            d.text("%s%s M%d %03d" % (marker, star, i + 1, vals[i]), 0, y, 255)
            d.bar(70, y, 56, 12, vals[i], 127)
            y += 14


class SystemPage(PageBase):
    title = "System"
    items = ["I2C Scan", "Control", "MIDI Ch", "Input", "Save", "Reload", "Panic"]

    def __init__(self, app):
        super().__init__(app)
        self.scan_cache = []
        self._control_before_edit = None
        self.offset = 0

    def on_event(self, ev):
        if not self.editing:
            if ev.delta != 0:
                self.sel = (self.sel + ev.delta) % len(self.items)
            if ev.click:
                item = self.items[self.sel]
                if item == "I2C Scan":
                    try:
                        self.scan_cache = amyboard.get_i2c().scan()
                        self.app.notice("I2C: " + ",".join([hex(x) for x in self.scan_cache]))
                    except Exception:
                        self.app.notice("I2C scan error")
                elif item == "Control":
                    self._control_before_edit = self.app.cfg["system"]["control_source"]
                    self.editing = True
                elif item == "MIDI Ch":
                    self.editing = True
                elif item == "Input":
                    self.app.notice("Input: " + self.app.input_driver.name)
                elif item == "Save":
                    ok = self.app.save_cfg() and self.app.save_state()
                    self.app.notice("Saved" if ok else "Save failed")
                elif item == "Reload":
                    self.app.pages["patches"].refresh()
                    self.app.notice("Patches reloaded")
                elif item == "Panic":
                    self.app.panic()
            if ev.long_press:
                self.app.back_to_menu()
            return

        # editing control source
        if self.items[self.sel] == "Control":
            if ev.delta != 0:
                modes = self.app.control_sources
                cur = self.app.cfg["system"]["control_source"]
                idx = modes.index(cur) if cur in modes else 0
                idx = (idx + ev.delta) % len(modes)
                self.app.cfg["system"]["control_source"] = modes[idx]
            if ev.click:
                self.editing = False
                self.app.apply_control_source(
                    self.app.cfg["system"]["control_source"], save=True, show_notice=True
                )
            if ev.long_press:
                if self._control_before_edit is not None:
                    self.app.cfg["system"]["control_source"] = self._control_before_edit
                self.editing = False
                self.app.back_to_menu()
            return

        # editing MIDI channel
        if self.items[self.sel] == "MIDI Ch":
            if ev.delta != 0:
                ch = self.app.cfg["system"]["midi_channel"]
                self.app.cfg["system"]["midi_channel"] = clamp(ch + ev.delta, 1, 16)
            if ev.click:
                self.editing = False
                self.app.save_cfg()
            if ev.long_press:
                self.editing = False
                self.app.back_to_menu()

    def render(self, d):
        d.text("System", 0, 0, 255)
        visible_count = 5
        if self.sel < self.offset:
            self.offset = self.sel
        elif self.sel >= self.offset + visible_count:
            self.offset = self.sel - visible_count + 1

        y = 20
        start = self.offset
        end = min(len(self.items), start + visible_count)
        for i in range(start, end):
            it = self.items[i]
            marker = ">" if i == self.sel else " "
            star = "*" if self.editing and i == self.sel else " "
            line = it
            if it == "Control":
                line = "Control:%s" % self.app.cfg["system"]["control_source"]
            elif it == "MIDI Ch":
                line = "MIDI Ch:%d" % self.app.cfg["system"]["midi_channel"]
            elif it == "Input":
                line = "Input:%s" % self.app.input_driver.name
            d.text("%s%s %s" % (marker, star, line), 0, y, 255)
            y += 14

class ScopePage(PageBase):
    title = "Scope"

    SOURCES = ["AUDIO CV1", "AUDIO CV2", "CV1 ROLL", "CV2 ROLL", "DUAL", "AMY OUT"]
    SHORT_SRC = ["AU1", "AU2", "CV1", "CV2", "DUL", "AMY"]
    SCALES = ["5V", "10V", "+/-5V"]
    SHORT_SCALE = ["5V", "10V", "+-5"]
    TIME_SCALES = ["0.5m", "1ms", "2ms", "5ms", "10m"]
    TIME_DELAYS_US = [35, 80, 180, 450, 1100]
    TIME_STRIDES = [1, 2, 3, 4, 6]

    NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    def __init__(self, app):
        super().__init__(app)
        self.source_idx = 0
        self.scale_idx = 0
        self.time_idx = 1  # Default: 1ms standard timebase
        self.hold = False

        self.edit_field = 0  # 0=Source, 1=Volt Scale, 2=Time Scale, 3=Hold

        # Data buffers (120 points wide to fit inside x=4..123)
        self.buf_width = 120
        self.roll_cv1 = [0.0] * self.buf_width
        self.roll_cv2 = [0.0] * self.buf_width
        self.last_burst = [0.0] * self.buf_width

        self.last_v = 0.0
        self.v_min = 0.0
        self.v_max = 0.0
        self.v_pp = 0.0

    def on_enter(self):
        self.editing = False

    def on_event(self, ev):
        if ev.long_press:
            self.app.back_to_menu()
            return

        if ev.click:
            # Click toggles between field selection and value editing
            if not self.editing:
                self.editing = True
            else:
                self.edit_field = (self.edit_field + 1) % 4
                if self.edit_field == 0:
                    self.editing = False
            return

        if ev.delta != 0:
            if not self.editing:
                # Fast switch channel/source by spinning encoder
                self.source_idx = (self.source_idx + ev.delta) % len(self.SOURCES)
            else:
                if self.edit_field == 0:
                    self.source_idx = (self.source_idx + ev.delta) % len(self.SOURCES)
                elif self.edit_field == 1:
                    self.scale_idx = (self.scale_idx + ev.delta) % len(self.SCALES)
                elif self.edit_field == 2:
                    self.time_idx = (self.time_idx + ev.delta) % len(self.TIME_SCALES)
                elif self.edit_field == 3:
                    self.hold = not self.hold
            return

    def _sample_burst(self, cv_channel):
        buf = []
        delay = self.TIME_DELAYS_US[self.time_idx]
        try:
            for _ in range(self.buf_width + 24):
                buf.append(float(amyboard.cv_in(cv_channel)))
                time.sleep_us(delay)
        except Exception:
            pass
        return buf

    def _map_y(self, v, y_top=16, y_bot=98):
        scale_mode = self.SCALES[self.scale_idx]
        if scale_mode == "5V":
            norm = clamp(v / 5.0, 0.0, 1.0)
        elif scale_mode == "10V":
            norm = clamp(v / 10.0, 0.0, 1.0)
        else:  # +/-5V
            norm = clamp((v + 5.0) / 10.0, 0.0, 1.0)
        return int(y_bot - norm * (y_bot - y_top))

    def _get_note_str(self, v):
        try:
            p = self.app._preset_values()
            scale = float(p.get("cv_pitch_scale", DEFAULT_CV_PITCH_SCALE))
            offset = float(p.get("cv_pitch_offset", DEFAULT_CV_PITCH_OFFSET))
            note_num = int(v * scale + offset)
            note_num = clamp(note_num, 0, 127)
            octave = (note_num // 12) - 1
            name = self.NOTE_NAMES[note_num % 12]
            return "%s%d (%d)" % (name, octave, note_num)
        except Exception:
            return "--"

    def render(self, d):
        # 1. Header Bar (y=0..12) - 4 Evenly Spaced Columns: [SRC] [VOLT] [TIME] [HOLD]
        src_label = self.SHORT_SRC[self.source_idx]
        scale_label = self.SHORT_SCALE[self.scale_idx]
        time_label = self.TIME_SCALES[self.time_idx]
        hold_label = "HLD" if self.hold else "RUN"

        # Highlight current edit field with prefix marker
        f0 = ">" if (self.editing and self.edit_field == 0) else " "
        f1 = ">" if (self.editing and self.edit_field == 1) else " "
        f2 = ">" if (self.editing and self.edit_field == 2) else " "
        f3 = ">" if (self.editing and self.edit_field == 3) else " "

        d.text("%s%s" % (f0, src_label), 0, 1, 255)
        d.text("%s%s" % (f1, scale_label), 34, 1, 255)
        d.text("%s%s" % (f2, time_label), 68, 1, 255)
        d.text("%s%s" % (f3, hold_label), 102, 1, 255)
        d.hline(0, 12, 128, 255)

        # 2. Scope Graticule Area (x=0, y=14, w=128, h=86)
        d.rect(0, 14, 128, 86, 255)
        # Dotted center zero/cross axes
        for x in range(2, 126, 6):
            d.pixel(x, 57, 255)
        for y in range(16, 98, 6):
            d.pixel(64, y, 255)

        src = self.source_idx

        # 3. Waveform processing and drawing
        if src in (0, 1):  # AUDIO CV1 or AUDIO CV2
            if not self.hold:
                raw = self._sample_burst(0 if src == 0 else 1)
                if raw:
                    self.v_min = min(raw)
                    self.v_max = max(raw)
                    self.v_pp = self.v_max - self.v_min
                    self.last_v = raw[-1]
                    avg = (self.v_min + self.v_max) / 2.0

                    trig = 0
                    if self.v_pp > 0.05:
                        for i in range(len(raw) - self.buf_width):
                            if raw[i] <= avg and raw[i + 1] > avg:
                                trig = i
                                break
                    self.last_burst = raw[trig : trig + self.buf_width]

            # Draw trace
            if len(self.last_burst) > 1:
                y_prev = self._map_y(self.last_burst[0], 16, 98)
                for i in range(1, len(self.last_burst)):
                    x0 = 3 + i - 1
                    x1 = 3 + i
                    y_curr = self._map_y(self.last_burst[i], 16, 98)
                    d.line(x0, y_prev, x1, y_curr, 255)
                    y_prev = y_curr

        elif src in (2, 3):  # CV1 ROLL or CV2 ROLL
            cv_idx = 0 if src == 2 else 1
            if not self.hold:
                try:
                    v = float(amyboard.cv_in(cv_idx))
                except Exception:
                    v = 0.0
                buf = self.roll_cv1 if src == 2 else self.roll_cv2
                buf.pop(0)
                buf.append(v)
                self.last_v = v
                self.v_min = min(buf)
                self.v_max = max(buf)
                self.v_pp = self.v_max - self.v_min

            buf = self.roll_cv1 if src == 2 else self.roll_cv2
            y_prev = self._map_y(buf[0], 16, 98)
            for i in range(1, len(buf)):
                x0 = 3 + i - 1
                x1 = 3 + i
                y_curr = self._map_y(buf[i], 16, 98)
                d.line(x0, y_prev, x1, y_curr, 255)
                y_prev = y_curr

        elif src == 4:  # DUAL (CV1 + CV2)
            if not self.hold:
                try:
                    v1 = float(amyboard.cv_in(0))
                    v2 = float(amyboard.cv_in(1))
                except Exception:
                    v1, v2 = 0.0, 0.0
                self.roll_cv1.pop(0)
                self.roll_cv1.append(v1)
                self.roll_cv2.pop(0)
                self.roll_cv2.append(v2)
                self.last_v = v1
                self.v_min = min(self.roll_cv1)
                self.v_max = max(self.roll_cv1)
                self.v_pp = self.v_max - self.v_min

            # Upper trace: CV1 in y=16..54
            d.text("1", 4, 16, 255)
            y_prev1 = self._map_y(self.roll_cv1[0], 16, 54)
            for i in range(1, len(self.roll_cv1)):
                x0 = 3 + i - 1
                x1 = 3 + i
                y_curr1 = self._map_y(self.roll_cv1[i], 16, 54)
                d.line(x0, y_prev1, x1, y_curr1, 255)
                y_prev1 = y_curr1

            # Lower trace: CV2 in y=60..98
            d.text("2", 4, 60, 255)
            y_prev2 = self._map_y(self.roll_cv2[0], 60, 98)
            for i in range(1, len(self.roll_cv2)):
                x0 = 3 + i - 1
                x1 = 3 + i
                y_curr2 = self._map_y(self.roll_cv2[i], 60, 98)
                d.line(x0, y_prev2, x1, y_curr2, 255)
                y_prev2 = y_curr2

        elif src == 5:  # SYNTH OUT (Real Live AMY Audio Output Buffer)
            if not self.hold:
                try:
                    import struct, amy
                    buf = amy.get_output_buffer()
                    if buf:
                        all_s = struct.unpack("<512h", buf)
                        stride = self.TIME_STRIDES[self.time_idx]
                        raw_audio = [all_s[i] / 32768.0 for i in range(0, len(all_s), 2 * stride)]
                        max_v = max(raw_audio)
                        min_v = min(raw_audio)
                        pp = max_v - min_v
                        
                        gain = 1.0
                        if pp > 0.005:
                            gain = clamp(1.8 / pp, 1.0, 8.0)

                        trig = 0
                        if pp > 0.01:
                            for i in range(len(raw_audio) - self.buf_width):
                                if raw_audio[i] <= 0.0 and raw_audio[i + 1] > 0.0:
                                    trig = i
                                    break
                        self.last_burst = [raw_audio[trig + i] * gain for i in range(min(self.buf_width, len(raw_audio) - trig))]
                        self.v_min = min_v * 5.0
                        self.v_max = max_v * 5.0
                        self.v_pp = pp * 5.0
                        self.last_v = raw_audio[-1] * 5.0
                except Exception:
                    pass

            if len(self.last_burst) > 1:
                y_center = 57
                y_span = 36
                y_prev = int(y_center - clamp(self.last_burst[0], -1.0, 1.0) * y_span)
                for i in range(1, len(self.last_burst)):
                    x0 = 3 + i - 1
                    x1 = 3 + i
                    y_curr = int(y_center - clamp(self.last_burst[i], -1.0, 1.0) * y_span)
                    d.line(x0, y_prev, x1, y_curr, 255)
                    y_prev = y_curr

        # 4. Telemetry Footer (y=103..127)
        d.text("V:%.2fV P-P:%.2fV" % (self.last_v, self.v_pp), 0, 103, 255)
        if src in (0, 2):  # CV1 / Pitch mode -> show 1V/Oct note
            note_str = self._get_note_str(self.last_v)
            d.text("Note:%s" % note_str, 0, 116, 255)
        elif src in (1, 3):  # CV2 / Gate mode -> show Gate state
            gate_state = "HIGH" if self.last_v >= DEFAULT_CV_GATE_ON else "LOW"
            d.text("Gate:%s (%.2fV)" % (gate_state, self.last_v), 0, 116, 255)
        elif src == 5:  # SYNTH OUT
            if self.v_pp > 0.05:
                if self.app._gate_prev and self.app._last_note >= 0:
                    note_i = int(clamp(self.app._last_note, 0, 127))
                    octave = (note_i // 12) - 1
                    name = self.NOTE_NAMES[note_i % 12]
                    d.text("Synth: %s%d ACTIVE" % (name, octave), 0, 116, 255)
                else:
                    d.text("Synth: PLAYING", 0, 116, 255)
            else:
                d.text("Synth: SILENT", 0, 116, 255)
        else:
            d.text("Min:%.2f Max:%.2f" % (self.v_min, self.v_max), 0, 116, 255)


class FXRackPage(PageBase):
    title = "FX Rack"

    ITEMS = [
        ("EXT IN", "ext_in", 0, 100, 10, "%d%%", 1),
        ("REV LV", "reverb_level", 0.0, 1.0, 0.05, "%d%%", 100),
        ("REV DM", "reverb_damp", 0.0, 0.95, 0.05, "%.2f", 1),
        ("REV RM", "reverb_room", 0.0, 0.95, 0.05, "%.2f", 1),
        ("CHO LV", "chorus_level", 0.0, 1.0, 0.05, "%d%%", 100),
        ("CHO DL", "chorus_delay", 8, 64, 4, "%d smp", 1),
        ("ECH LV", "echo_level", 0.0, 1.0, 0.05, "%d%%", 100),
        ("ECH TM", "echo_time", 20, 1000, 25, "%d ms", 1),
        ("ECH FB", "echo_feedback", 0.0, 0.85, 0.05, "%d%%", 100),
        ("RESON",  "resonance", 0.7, 8.0, 0.2, "%.1f", 1),
    ]

    def __init__(self, app):
        super().__init__(app)
        self.selected_idx = 0

    def on_enter(self):
        self.editing = False

    def on_event(self, ev):
        if ev.long_press:
            self.app.back_to_menu()
            return

        if ev.click:
            self.editing = not self.editing
            if not self.editing:
                self.app.save_state()
            return

        if ev.delta != 0:
            if not self.editing:
                self.selected_idx = (self.selected_idx + ev.delta) % len(self.ITEMS)
            else:
                label, key, v_min, v_max, step, fmt, mult = self.ITEMS[self.selected_idx]
                fx_cfg = self.app.cfg.setdefault("fx", {})
                cur = float(fx_cfg.get(key, DEFAULT_CFG["fx"].get(key, v_min)))
                new_val = clamp(cur + ev.delta * step, v_min, v_max)
                if isinstance(v_min, int) and isinstance(step, int):
                    new_val = int(round(new_val))
                fx_cfg[key] = new_val
                self.app.apply_fx()

    def render(self, d):
        d.text("FX RACK", 0, 1, 255)
        mode_str = "EDIT" if self.editing else "SEL"
        d.text("[%s]" % mode_str, 88, 1, 255)
        d.hline(0, 12, 128, 255)

        visible_count = 7
        offset = clamp(self.selected_idx - 3, 0, max(0, len(self.ITEMS) - visible_count))
        
        y = 16
        fx_cfg = self.app.cfg.setdefault("fx", {})
        for i in range(offset, min(len(self.ITEMS), offset + visible_count)):
            label, key, v_min, v_max, step, fmt, mult = self.ITEMS[i]
            cur = float(fx_cfg.get(key, DEFAULT_CFG["fx"].get(key, v_min)))
            is_sel = (i == self.selected_idx)
            marker = ">" if is_sel else " "

            d.text("%s%s" % (marker, label[:6]), 0, y, 255)

            val_disp = cur * mult
            val_str = fmt % val_disp
            d.text(val_str[:5], 60, y, 255)

            norm = clamp((cur - v_min) / (v_max - v_min) if v_max > v_min else 0.0, 0.0, 1.0)
            bar_w = int(norm * 22)
            d.rect(98, y + 1, 24, 7, 255)
            if bar_w > 0:
                d.fill_rect(98, y + 1, bar_w, 7, 255)

            y += 14

        d.hline(0, 116, 128, 255)
        rev_on = fx_cfg.get("reverb_level", 0.0) > 0.01
        cho_on = fx_cfg.get("chorus_level", 0.0) > 0.01
        ech_on = fx_cfg.get("echo_level", 0.0) > 0.01
        d.text("R:%s C:%s E:%s" % ("ON" if rev_on else "--", "ON" if cho_on else "--", "ON" if ech_on else "--"), 0, 118, 255)


_EUC_CACHE = {}

def generate_euclidean(hits, steps):
    if steps <= 0: return [0]
    hits = max(0, min(steps, hits))
    key = (hits, steps)
    if key in _EUC_CACHE:
        return _EUC_CACHE[key]
    if hits == 0:
        res = [0] * steps
    elif hits == steps:
        res = [1] * steps
    else:
        pattern = []
        bucket = 0
        for _ in range(steps):
            bucket += hits
            if bucket >= steps:
                bucket -= steps
                pattern.append(1)
            else:
                pattern.append(0)
        res = pattern
    _EUC_CACHE[key] = res
    return res


class SequencerPage(PageBase):
    title = "Sequencer"

    SCALES = [
        ("Min Pent", [0, 3, 5, 7, 10]),
        ("Maj Pent", [0, 2, 4, 7, 9]),
        ("Dorian",   [0, 2, 3, 5, 7, 9, 10]),
        ("Minor",    [0, 2, 3, 5, 7, 8, 10]),
        ("Major",    [0, 2, 4, 5, 7, 9, 11]),
        ("Hirajoshi",[0, 2, 3, 7, 8]),
        ("Insen",    [0, 1, 5, 7, 10]),
        ("Blues",    [0, 3, 5, 6, 7, 10]),
        ("WholeTone",[0, 2, 4, 6, 8, 10]),
        ("Chromatic",[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]),
    ]
    NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    FIELDS = ["STATE", "BPM", "STEPS", "HITS", "ROTATE", "MUTATE", "SCALE", "ROOT", "OCT", "GATE"]

    def __init__(self, app):
        super().__init__(app)
        self.edit_field = 0
        self.editing = False

    def on_enter(self):
        self.editing = False

    def on_event(self, ev):
        if ev.long_press:
            self.app.back_to_menu()
            return

        seq = self.app.cfg.setdefault("sequencer", {})

        if ev.click:
            if self.edit_field == 0:
                seq["running"] = not seq.get("running", False)
                if not seq["running"]:
                    self.app.sequencer_stop()
            else:
                self.editing = not self.editing
            return

        if ev.delta != 0:
            if not self.editing:
                self.edit_field = (self.edit_field + ev.delta) % len(self.FIELDS)
            else:
                field = self.FIELDS[self.edit_field]
                if field == "STATE":
                    seq["running"] = not seq.get("running", False)
                    if not seq["running"]:
                        self.app.sequencer_stop()
                elif field == "BPM":
                    bpm = seq.get("bpm", 120)
                    if bpm == 0 and ev.delta > 0:
                        seq["bpm"] = 40
                    elif bpm <= 40 and ev.delta < 0:
                        seq["bpm"] = 0
                    else:
                        seq["bpm"] = clamp(bpm + ev.delta * 2, 40, 240)
                elif field == "STEPS":
                    seq["steps"] = clamp(seq.get("steps", 16) + ev.delta, 2, 16)
                    if seq.get("hits", 5) > seq["steps"]:
                        seq["hits"] = seq["steps"]
                elif field == "HITS":
                    seq["hits"] = clamp(seq.get("hits", 5) + ev.delta, 0, seq.get("steps", 16))
                elif field == "ROTATE":
                    seq["rotate"] = (seq.get("rotate", 0) + ev.delta) % seq.get("steps", 16)
                elif field == "MUTATE":
                    seq["mutate"] = clamp(seq.get("mutate", 15) + ev.delta * 5, 0, 100)
                elif field == "SCALE":
                    cur_idx = seq.get("scale_idx", 0)
                    seq["scale_idx"] = (cur_idx + ev.delta) % len(self.SCALES)
                elif field == "ROOT":
                    seq["root"] = clamp(seq.get("root", 48) + ev.delta, 24, 72)
                elif field == "OCT":
                    seq["octaves"] = clamp(seq.get("octaves", 2) + ev.delta, 1, 4)
                elif field == "GATE":
                    seq["gate"] = clamp(seq.get("gate", 50) + ev.delta * 5, 10, 90)

    def render(self, d):
        seq = self.app.cfg.setdefault("sequencer", {})
        running = seq.get("running", False)
        bpm = seq.get("bpm", 120)
        steps = seq.get("steps", 16)
        hits = seq.get("hits", 5)
        rotate = seq.get("rotate", 0)
        mutate = seq.get("mutate", 15)
        scale_idx = seq.get("scale_idx", 0)
        root = seq.get("root", 48)
        octs = seq.get("octaves", 2)
        gate = seq.get("gate", 50)

        scale_name, _ = self.SCALES[scale_idx]

        status_str = "[RUN]" if running else "[STP]"
        bpm_str = "EXT" if bpm == 0 else ("%d" % bpm)
        d.text("%s %s" % (status_str, bpm_str), 0, 1, 255)
        d.text("E:%d/%d" % (hits, steps), 80, 1, 255)
        d.hline(0, 12, 128, 255)

        raw_euc = generate_euclidean(hits, steps)
        euc = [raw_euc[(i - rotate) % steps] for i in range(steps)]
        curr_step = self.app.seq_step % steps if running else -1

        for i in range(steps):
            col = i % 8
            row = i // 8
            bx = 4 + col * 15
            by = 16 + row * 16

            d.rect(bx, by, 13, 13, 255)

            if euc[i]:
                d.fill_rect(bx + 3, by + 3, 7, 7, 255)

            if i == curr_step:
                d.rect(bx - 1, by - 1, 15, 15, 255)
                if not euc[i]:
                    d.line(bx + 2, by + 2, bx + 10, by + 10, 255)
                    d.line(bx + 2, by + 10, bx + 10, by + 2, 255)

        root_name = self.NOTE_NAMES[root % 12]
        root_oct = (root // 12) - 1
        if running and self.app.seq_last_note >= 0:
            ln = self.app.seq_last_note
            ln_name = self.NOTE_NAMES[ln % 12]
            ln_oct = (ln // 12) - 1
            d.text("S%d %s%d (%d)" % (curr_step + 1, ln_name, ln_oct, ln), 0, 50, 255)
        else:
            d.text("%s %s%d" % (scale_name[:8], root_name, root_oct), 0, 50, 255)
        d.hline(0, 60, 128, 255)

        params = [
            ("STATE", status_str),
            ("BPM", "EXT" if bpm == 0 else "%d" % bpm),
            ("STEPS", "%d" % steps),
            ("HITS", "%d" % hits),
            ("ROT", "%d" % rotate),
            ("MUTATE", "%d%%" % mutate),
            ("SCALE", scale_name[:9]),
            ("ROOT", "%s%d" % (root_name, root_oct)),
            ("OCT", "%d" % octs),
            ("GATE", "%d%%" % gate),
        ]

        visible_count = 4
        offset = clamp(self.edit_field - 1, 0, max(0, len(params) - visible_count))
        y = 64
        for i in range(offset, min(len(params), offset + visible_count)):
            pname, pval = params[i]
            is_sel = (i == self.edit_field)
            marker = ">" if is_sel else " "
            star = "*" if (is_sel and self.editing) else " "
            d.text("%s%s%s" % (marker, star, pname), 0, y, 255)
            d.text(pval, 68, y, 255)
            y += 15


# -----------------------------
# App
# -----------------------------
DEFAULT_CFG = {
    "patches": {"current": ""},
    "preset_voice": {
        "synth": DEFAULT_PRESET_SYNTH,
        "patch": 0,
        "num_voices": 1,
        "filter_type": DEFAULT_FILTER_TYPE,
        "filter_cutoff": DEFAULT_FILTER_CUTOFF,
        "cv_pitch_input": DEFAULT_CV_PITCH_INPUT,
        "cv_gate_input": DEFAULT_CV_GATE_INPUT,
        "cv_gate_on": DEFAULT_CV_GATE_ON,
        "cv_gate_off": DEFAULT_CV_GATE_OFF,
        "cv_pitch_scale": DEFAULT_CV_PITCH_SCALE,
        "cv_pitch_offset": DEFAULT_CV_PITCH_OFFSET,
    },
    "fx": {
        "ext_in": 0,
        "reverb_level": 0.0,
        "reverb_damp": 0.3,
        "reverb_room": 0.5,
        "chorus_level": 0.0,
        "chorus_delay": 32,
        "echo_level": 0.0,
        "echo_time": 250,
        "echo_feedback": 0.4,
        "resonance": 1.0,
    },
    "sequencer": {
        "running": False,
        "bpm": 120,
        "steps": 16,
        "hits": 5,
        "rotate": 0,
        "mutate": 15,
        "scale_idx": 0,
        "root": 48,
        "octaves": 2,
        "gate": 50,
    },
    "drums": {
        "running": False,
        "bpm": 120,
        "tracks": [
            {"hits": 4, "steps": 16, "rotate": 0, "mute": False, "vol": 90},
            {"hits": 2, "steps": 16, "rotate": 4, "mute": False, "vol": 85},
            {"hits": 8, "steps": 16, "rotate": 0, "mute": False, "vol": 70},
            {"hits": 3, "steps": 12, "rotate": 2, "mute": False, "vol": 75},
        ]
    },
    "envelope": {
        "target": "AMP",
        "attack": 15,
        "decay": 250,
        "sustain": 70,
        "release": 450,
    },
    "lfos": [
        {"wave": "Sine", "rate": 1.0, "depth": 50, "dest": "None"},
        {"wave": "Triangle", "rate": 0.5, "depth": 50, "dest": "None"},
    ],
    "voice_mode": {"polyphony": 6, "unison": False, "detune": 12, "spread": 18},
    "cv_routing": {
        "routes": [
            {"target": "none", "amount": 0, "polarity": 1, "smooth": 20},
            {"target": "none", "amount": 0, "polarity": 1, "smooth": 20},
            {"target": "pitch", "amount": 100, "polarity": 1, "smooth": 0},
            {"target": "gate", "amount": 100, "polarity": 1, "smooth": 0},
        ]
    },
    "macros": {"values": [64, 64, 64, 64]},
    "system": {"midi_channel": 1, "control_source": INPUT_MODE},
}

DEFAULT_STATE = {"menu_index": 0, "current_page": "menu"}

DX7_NAMES = [
    "BRASS 1", "BRASS 2", "STRINGS 1", "STRINGS 2", "SYN-ORCH", "PIANO 1", "PIANO 2", "PIANO 3",
    "E.PIANO 1", "GUITAR 1", "GUITAR 2", "SYN-LEAD 1", "BASS 1", "BASS 2", "E.ORGAN 1", "PIPES 1",
    "HARPSICH 1", "CLAV 1", "VIBE 1", "MARIMBA", "TUB BELLS", "VOICE 1", "RECORDER", "SOLO VIO",
    "GLOCKENS", "TRUMPET 1", "HORN", "CALLIOPE", "SYN-BASS 1", "TIMPANI", "SNARE DRUM", "KICK DRUM",
    "BRASS 3", "STRINGS 3", "SYN-ORCH 2", "E.PIANO 2", "E.PIANO 3", "E.ORGAN 2", "HARP 1", "KOTO",
    "SITAR", "SLAP BASS", "SYN-BASS 2", "FRETLESS", "FLUTE 1", "OBOE 1", "CLARINET", "BASSOON",
    "ACCORDION", "HARMONICA", "STEEL DRUM", "XYLOPHONE", "CELESTA", "BELLS", "VOICE 2", "WHISTLE",
    "CHIME", "SNARE 2", "TOM TOM", "CYMBAL", "SPLASH", "COWBELL", "WOOD BLOCK", "CLAPS",
    "SPACE PAD", "DIGI-LOG", "FUNK CLAV", "ANALOG BASS", "WARM STRINGS", "GLASS VOX", "DIGI BELLS", "ICE PLUCK",
    "ORGAN 3", "ORGAN 4", "JAZZ GUITAR", "FUNK BASS", "POLY SYNTH", "SWEEP LEAD", "RESO LEAD", "SYNC LEAD",
    "CRYSTAL", "CELLO", "VIOLIN", "FRENCH HORN", "TROMBONE", "SAX", "PAN FLUTE", "SHAKUHACHI",
    "KALIMBA", "GAMELAN", "TIMBALE", "AGOGO", "TAMBOURINE", "CONGA", "SHAKER", "DRUM SET",
    "BELL PAD", "SYN-VOX", "HARP 2", "WARM PAD", "SOLO CELLO", "MUTED TRUMP", "SYN-CLAV", "TOUCH ORGAN",
    "WINE GLASS", "LOG DRUM", "SYN-PIANO", "MELLOW HORN", "FANTASIA", "ATMOSPHERE", "VOX HUMANA", "SOLO SYNTH",
    "TECHNO BASS", "POP BRASS", "SOLO FLUTE", "CHURCH BELL", "VIBES 2", "ELECTRIC 12", "SYNTH-STRING", "ORCHESTRAL",
    "FRETLESS 2", "JAZZ ORGAN", "SAW LEAD", "SQUARE LEAD", "SOFT STRINGS", "FAT BASS", "DIGITAL PAD", "PERCUSSION"
]

JUNO_NAMES = [
    "Brass 1", "Brass 2", "Horn 1", "Trumpet 1", "Flute", "Pipes", "Organ 1", "Organ 2",
    "Strings 1", "Strings 2", "Cello 1", "Violin 1", "Pizzicato", "Harp", "Bass 1", "Bass 2",
    "Piano 1", "Piano 2", "E.Piano 1", "E.Piano 2", "Harpsi 1", "Harpsi 2", "Clav 1", "Clav 2",
    "Synth Pad", "Warm Pad", "Sweep Pad", "Space Pad", "Bell 1", "Bell 2", "Vibes", "Marimba",
    "Lead 1", "Lead 2", "Sync Lead", "Reso Lead", "Pulse Lead", "Square Lead", "Saw Lead", "Whistle",
    "Funk Clav", "Pluck", "Arp Synth", "Chirp", "Laser", "Staccato", "Oct Synth", "Fat Saw",
    "PWM Strings", "Soft Brass", "Moog Bass", "Acid Bass", "Sub Bass", "Slap Bass", "Chorused", "Phase Pad",
    "Echo Synth", "Trance Pad", "Voice Lead", "Calliope", "Tubular", "Steel Pan", "Tom Drum", "SFX Noise",
    "Brass 3", "Soft Horn", "Trombone", "Muted Brass", "Pan Flute", "Church Org", "Jazz Organ", "Rock Organ",
    "Slow Strings", "Chamber Str", "Pizz Str", "Solo Cello", "Sitar 1", "Koto 1", "Fretless", "Synth Bass 3",
    "Honky Tonk", "Tack Piano", "Wurlitzer", "Rhodes Pad", "Harpsichord", "Spinet", "Funk Synth", "Mute Clav",
    "Analog Pad", "Glass Pad", "Air Pad", "Solar Wind", "Chimes", "Glocken", "Xylophone", "Celesta",
    "Fifth Lead", "Mono Lead", "Searing Saw", "Ring Mod", "Filter Lead", "Glide Lead", "Solo Saw", "Ocarina",
    "Wah Clav", "Guitar Synth", "Muted Pluck", "Zap Synth", "SciFi FX", "Short Stab", "Dual Saw", "Super Saw",
    "Orch Strings", "Brass Ens", "House Bass", "Reso Bass 2", "Deep Sub", "Pick Bass", "Dimension", "Rotary Pad",
    "Digital Pad", "Vocal Pad", "Sweep Synth", "Techno Pad", "Crystal Vox", "Steam Organ", "Gong", "Woodblock"
]


class MenuApp:
    control_sources = list(CONTROL_SOURCE_OPTIONS)

    def __init__(self):
        self.cfg = merge_missing(deep_copy(safe_read_json(CONFIG_PATH, DEFAULT_CFG)), DEFAULT_CFG)
        self.state = merge_missing(deep_copy(safe_read_json(STATE_PATH, DEFAULT_STATE)), DEFAULT_STATE)
        self._normalize_cfg()

        self.display = Display(rotate=DISPLAY_ROTATE)
        self.input_driver = make_input_driver(
            self.cfg["system"]["control_source"], midi_channel_getter=self.get_midi_channel
        )

        self.pages = {
            "perform": PerformPage(self),
            "group_synth": GroupPage(self, "Synthesizer", 
                                     ["Preset Voice", "Filter Bode", "Filter Type", "ADSR Envelope", "Voice Mode"], 
                                     ["preset_voice", "filt_cut", "filt_type", "envelope", "voice_mode"]),
            "group_seq": GroupPage(self, "Rhythm & Seq", 
                                   ["Melodic Seq", "Drum Machine"], 
                                   ["sequencer", "drums"]),
            "group_mod": GroupPage(self, "Modulation", 
                                   ["Dual LFOs", "Macros", "CV Routing"], 
                                   ["lfos", "macros", "cv_routing"]),
            "group_sys": GroupPage(self, "System & SD", 
                                   ["Patch Profiles", "System Diag"], 
                                   ["patches", "system"]),
            # Sub-pages
            "preset_voice": PresetVoicePage(self),
            "filt_cut": FilterCutoffPage(self),
            "filt_type": FilterTypePage(self),
            "envelope": EnvPage(self),
            "voice_mode": VoiceModePage(self),
            "sequencer": SequencerPage(self),
            "drums": DrumMachinePage(self),
            "lfos": LFOPage(self),
            "macros": MacrosPage(self),
            "cv_routing": CVRoutingPage(self),
            "fx": FXRackPage(self),
            "scope": ScopePage(self),
            "patches": PatchesPage(self),
            "system": SystemPage(self),
        }

        self.menu_items = [
            "Performance",
            "Synthesizer",
            "Rhythm & Seq",
            "Modulation",
            "Master FX",
            "Oscilloscope",
            "System & SD",
        ]
        self.menu_keys = [
            "perform",
            "group_synth",
            "group_seq",
            "group_mod",
            "fx",
            "scope",
            "group_sys",
        ]

        self.in_page = False
        self.page_stack = []
        self.current_page_key = None
        self._gate_prev = False
        self._last_note = -1
        self.audition_off_time = None
        self.menu_index = 0
        self.menu_offset = 0
        self.notice_msg = ""
        self.notice_until = 0

        # Engines
        self.seq_step = 0
        self.seq_last_tick = time.ticks_ms()
        self.seq_last_note = -1
        self.seq_gate_active = False
        self.seq_gate_off_time = time.ticks_ms()
        self.seq_ext_clock_prev = False
        self.seq_turing_reg = 0xACE1

        self.drum_step = 0
        self.drum_last_tick = time.ticks_ms()
        self.lfo_last_tick = time.ticks_ms()

        self.apply_preset_voice(save=False, show_notice=False)
        self.apply_fx()
        self.apply_envelope()

    def _normalize_cfg(self):
        self.cfg = merge_missing(deep_copy(self.cfg), DEFAULT_CFG)
        try:
            midi_ch = int(self.cfg["system"].get("midi_channel", 1))
        except Exception:
            midi_ch = 1
        self.cfg["system"]["midi_channel"] = clamp(midi_ch, 1, 16)
        mode = str(self.cfg["system"].get("control_source", INPUT_MODE)).lower()
        if mode not in self.control_sources:
            mode = INPUT_MODE if INPUT_MODE in self.control_sources else "hybrid"
        self.cfg["system"]["control_source"] = mode
        cur = self.cfg.get("patches", {}).get("current", "")
        self.cfg["patches"]["current"] = str(cur) if cur is not None else ""
        return self.cfg

    def _ensure_dir(self, path):
        if is_dir(path):
            return True
        try:
            os.mkdir(path)
            return True
        except Exception:
            return False

    def _next_profile_path(self):
        i = 1
        while i < 1000:
            path = PATCH_PROFILE_DIR + "/profile%03d.patch" % i
            try:
                os.stat(path)
                i += 1
            except Exception:
                return path
        return PATCH_PROFILE_DIR + "/profile999.patch"

    def save_patch_profile(self):
        if not self._ensure_dir(PATCH_PROFILE_DIR):
            return None
        path = self._next_profile_path()
        payload = {
            "format": PATCH_PROFILE_FORMAT,
            "version": PATCH_PROFILE_VERSION,
            "cfg": deep_copy(self.cfg),
        }
        if not safe_write_json(path, payload):
            return None
        self.cfg["patches"]["current"] = path
        self.save_cfg()
        return path

    def load_patch_profile(self, path):
        raw = safe_read_json(path, None)
        if not isinstance(raw, dict):
            return "error"
        cfg = raw.get("cfg")
        if not isinstance(cfg, dict):
            cfg = raw
        if not isinstance(cfg, dict):
            return "error"

        self.cfg = merge_missing(deep_copy(cfg), DEFAULT_CFG)
        self._normalize_cfg()
        self.cfg["patches"]["current"] = path
        self.apply_control_source(
            self.cfg["system"]["control_source"], save=False, show_notice=False
        )
        applied = self.apply_preset_voice(save=False, show_notice=False)
        self.apply_fx()
        self.apply_envelope()
        self.save_cfg()
        if applied:
            return "loaded"
        return "loaded_cfg_only"

    def _preset_values(self):
        p = self.cfg.get("preset_voice", {})
        if not isinstance(p, dict):
            p = deep_copy(DEFAULT_CFG["preset_voice"])
        p.setdefault("synth", DEFAULT_PRESET_SYNTH)
        p.setdefault("patch", 0)
        p.setdefault("num_voices", 1)
        p.setdefault("cv_pitch_input", DEFAULT_CV_PITCH_INPUT)
        p.setdefault("cv_gate_input", DEFAULT_CV_GATE_INPUT)
        p.setdefault("cv_gate_on", DEFAULT_CV_GATE_ON)
        p.setdefault("cv_gate_off", DEFAULT_CV_GATE_OFF)
        p.setdefault("cv_pitch_scale", DEFAULT_CV_PITCH_SCALE)
        p.setdefault("cv_pitch_offset", DEFAULT_CV_PITCH_OFFSET)
        try:
            synth = int(p.get("synth", DEFAULT_PRESET_SYNTH))
        except Exception:
            synth = DEFAULT_PRESET_SYNTH
        p["synth"] = clamp(synth, 1, 4)
        try:
            patch = int(p.get("patch", BUILTIN_PATCH_MIN))
        except Exception:
            patch = BUILTIN_PATCH_MIN
        p["patch"] = clamp(patch, BUILTIN_PATCH_MIN, BUILTIN_PATCH_MAX)
        try:
            num_voices = int(p.get("num_voices", 1))
        except Exception:
            num_voices = 1
        p["num_voices"] = clamp(num_voices, 1, 16)
        try:
            p["cv_pitch_input"] = int(p.get("cv_pitch_input", DEFAULT_CV_PITCH_INPUT))
        except Exception:
            p["cv_pitch_input"] = DEFAULT_CV_PITCH_INPUT
        try:
            p["cv_gate_input"] = int(p.get("cv_gate_input", DEFAULT_CV_GATE_INPUT))
        except Exception:
            p["cv_gate_input"] = DEFAULT_CV_GATE_INPUT
        try:
            p["cv_gate_on"] = float(p.get("cv_gate_on", DEFAULT_CV_GATE_ON))
        except Exception:
            p["cv_gate_on"] = DEFAULT_CV_GATE_ON
        try:
            p["cv_gate_off"] = float(p.get("cv_gate_off", DEFAULT_CV_GATE_OFF))
        except Exception:
            p["cv_gate_off"] = DEFAULT_CV_GATE_OFF
        try:
            p["cv_pitch_scale"] = float(p.get("cv_pitch_scale", DEFAULT_CV_PITCH_SCALE))
        except Exception:
            p["cv_pitch_scale"] = DEFAULT_CV_PITCH_SCALE
        try:
            p["cv_pitch_offset"] = float(p.get("cv_pitch_offset", DEFAULT_CV_PITCH_OFFSET))
        except Exception:
            p["cv_pitch_offset"] = DEFAULT_CV_PITCH_OFFSET
        p["filter_type"] = normalize_filter_type(p.get("filter_type", DEFAULT_FILTER_TYPE))
        try:
            filter_cutoff = int(p.get("filter_cutoff", DEFAULT_FILTER_CUTOFF))
        except Exception:
            filter_cutoff = DEFAULT_FILTER_CUTOFF
        p["filter_cutoff"] = clamp(filter_cutoff, 100, 12000)
        self.cfg["preset_voice"] = p
        return p

    def patch_label(self, patch):
        p = int(patch)
        if p < len(JUNO_NAMES):
            return JUNO_NAMES[p]
        if p < 128:
            return "Juno-%02d" % p
        if p < 256:
            dx_idx = p - 128
            if dx_idx < len(DX7_NAMES):
                return DX7_NAMES[dx_idx]
            return "DX7-%02d" % dx_idx
        if p == 256:
            return "Grand Piano"
        if p == 257:
            return "Web Bass"
        return "Patch-%d" % p

    def apply_cv_play_mapping(self):
        return True

    def apply_filter_type(self, save=False, show_notice=False):
        p = self._preset_values()
        kind = normalize_filter_type(p.get("filter_type", DEFAULT_FILTER_TYPE))
        p["filter_type"] = kind
        cutoff = int(p.get("filter_cutoff", DEFAULT_FILTER_CUTOFF))
        try:
            import amy
            amy.send(
                synth=p["synth"],
                osc=0,
                filter_type=filter_type_to_amy_value(kind),
                filter_freq=cutoff,
            )
            ok = True
        except Exception as e:
            print("Filter error:", e)
            ok = False

        if show_notice:
            if ok:
                self.notice("Filt:%s %dHz" % (kind, cutoff))
            else:
                self.notice("Filter err")
        if save:
            self.save_cfg()
        return ok

    def apply_preset_voice(self, save=False, show_notice=False):
        p = self._preset_values()
        try:
            import amy
            amy.send(
                synth=p["synth"],
                patch=p["patch"],
                num_voices=p["num_voices"],
                filter_type=filter_type_to_amy_value(p["filter_type"]),
                filter_freq=p["filter_cutoff"],
            )
            ok = True
        except Exception as e:
            print("Voice error:", e)
            ok = False

        if show_notice:
            if ok:
                self.notice("Preset ready")
            else:
                self.notice("Preset err")
        if save:
            self.save_cfg()
        return ok

    def apply_control_source(self, mode, save=False, show_notice=False):
        mode = str(mode).lower()
        if mode not in self.control_sources:
            mode = "hybrid"
        self.cfg["system"]["control_source"] = mode
        driver = make_input_driver(mode, midi_channel_getter=self.get_midi_channel)
        ok = driver.enabled if hasattr(driver, "enabled") else True
        if ok or mode in ("computer", "demo", "hybrid"):
            self.input_driver = driver
        else:
            self.input_driver = make_input_driver("hybrid", midi_channel_getter=self.get_midi_channel)
            self.cfg["system"]["control_source"] = "hybrid"

        if show_notice:
            self.notice("Ctrl:%s" % self.input_driver.name[:10])
        if save:
            self.save_cfg()
        return True

    def get_midi_channel(self):
        try:
            return int(self.cfg["system"].get("midi_channel", 1))
        except Exception:
            return 1

    def panic(self):
        try:
            import amy
            amy.send(vel=0)
            amy.reset()
            self.apply_preset_voice(save=False, show_notice=False)
            self.apply_fx()
            self.apply_envelope()
        except Exception:
            pass
        self._gate_prev = False
        self._last_note = -1

    def save_cfg(self):
        return safe_write_json(CONFIG_PATH, self.cfg)

    def load_cfg(self):
        self.cfg = merge_missing(deep_copy(safe_read_json(CONFIG_PATH, DEFAULT_CFG)), DEFAULT_CFG)
        self._normalize_cfg()

    def save_state(self):
        payload = {"menu_index": self.menu_index, "current_page": "menu"}
        return safe_write_json(STATE_PATH, payload)

    def load_state(self):
        self.state = merge_missing(deep_copy(safe_read_json(STATE_PATH, DEFAULT_STATE)), DEFAULT_STATE)

    def notice(self, msg, ms=1500):
        self.notice_msg = msg
        self.notice_until = time.ticks_add(time.ticks_ms(), ms)

    def current_page(self):
        if self.current_page_key and self.current_page_key in self.pages:
            return self.pages[self.current_page_key]
        return None

    def open_page(self, key):
        if self.in_page and self.current_page_key:
            self.page_stack.append(self.current_page_key)
        else:
            self.page_stack = []
        self.in_page = True
        self.current_page_key = key
        p = self.current_page()
        if p:
            p.on_enter()

    def back_to_menu(self):
        if self.page_stack:
            prev = self.page_stack.pop()
            self.current_page_key = prev
            p = self.current_page()
            if p:
                p.on_enter()
        else:
            self.in_page = False
            self.current_page_key = None
        self.save_state()

    def handle_event(self, ev):
        if (not self.in_page) and ev.long_press:
            self.panic()
            self.notice("PANIC: ALL OFF")
            return

        if not self.in_page:
            if ev.delta != 0:
                self.menu_index = (self.menu_index + ev.delta) % len(self.menu_items)
            if ev.click:
                key = self.menu_keys[self.menu_index]
                self.open_page(key)
            return

        p = self.current_page()
        if p:
            p.on_event(ev)

    def render_menu(self):
        d = self.display
        d.text("AMYBOARD EURORACK", 0, 1, 255)
        d.hline(0, 12, 128, 255)

        visible_count = 7
        if self.menu_index < self.menu_offset:
            self.menu_offset = self.menu_index
        elif self.menu_index >= self.menu_offset + visible_count:
            self.menu_offset = self.menu_index - visible_count + 1

        y = 16
        start = self.menu_offset
        end = min(len(self.menu_items), start + visible_count)
        for i in range(start, end):
            item = self.menu_items[i]
            is_active = (i == self.menu_index)
            marker = ">" if is_active else " "
            d.text("%s %s" % (marker, item[:13]), 0, y, 255)
            y += 16

        total_items = len(self.menu_items)
        if total_items > visible_count:
            track_h = 108
            thumb_h = max(12, int((visible_count / total_items) * track_h))
            thumb_y = 16 + int((self.menu_index / (total_items - 1)) * (track_h - thumb_h))
            d.vline(126, 16, track_h, 255)
            d.fill_rect(125, thumb_y, 3, thumb_h, 255)

    def render(self):
        d = self.display
        d.clear()
        if not self.in_page:
            self.render_menu()
        else:
            p = self.current_page()
            if p:
                p.render(d)

        now = time.ticks_ms()
        if self.notice_msg and time.ticks_diff(self.notice_until, now) > 0:
            d.fill_rect(2, 110, 124, 17, 0)
            d.rect(2, 110, 124, 17, 255)
            d.text(self.notice_msg[:15], 6, 115, 255)

        d.refresh()

    def apply_fx(self):
        try:
            import amy
            fx = self.cfg.setdefault("fx", {})
            
            ext_in = int(fx.get("ext_in", 0))
            if ext_in > 0:
                ext_gain = ext_in / 100.0
                wave_in = getattr(amy, "AUDIO_IN0", getattr(amy, "AUDIO_EXT0", 0))
                amy.send(osc=30, wave=wave_in, vel=ext_gain)
            else:
                try:
                    amy.send(osc=30, vel=0)
                except Exception:
                    pass

            rev_lvl = float(fx.get("reverb_level", 0.0))
            rev_dmp = float(fx.get("reverb_damp", 0.3))
            rev_room = float(fx.get("reverb_room", 0.5))
            if rev_lvl > 0.001:
                liveness = clamp(rev_room, 0.0, 0.95)
                damping = clamp(rev_dmp, 0.0, 0.95)
                amy.reverb(rev_lvl, liveness, damping, 3000)
            else:
                amy.reverb(0.0)

            cho_lvl = float(fx.get("chorus_level", 0.0))
            cho_del = int(fx.get("chorus_delay", 32))
            if cho_lvl > 0.001:
                amy.chorus(cho_lvl, cho_del)
            else:
                amy.chorus(0.0)

            ech_lvl = float(fx.get("echo_level", 0.0))
            ech_time = int(fx.get("echo_time", 250))
            ech_fdbk = clamp(float(fx.get("echo_feedback", 0.4)), 0.0, 0.85)
            if ech_lvl > 0.001:
                delay_l = ech_time
                delay_r = int(ech_time * 0.75) if ech_time > 40 else ech_time
                amy.echo(ech_lvl, delay_l, delay_r, ech_fdbk, ech_fdbk)
            else:
                amy.echo(0.0)

            p = self._preset_values()
            res = float(fx.get("resonance", 1.0))
            amy.send(synth=p["synth"], resonance=res)
        except Exception:
            pass

    def apply_envelope(self):
        try:
            import amy
            env = self.cfg.get("envelope", {})
            p = self._preset_values()
            att = env.get("attack", 15)
            dec = env.get("decay", 250)
            sus = env.get("sustain", 70) / 100.0
            rel = env.get("release", 450)
            
            bp_str = "0,0,%d,1.0,%d,%.2f,%d,0" % (att, att + dec, sus, rel)
            if env.get("target", "AMP") == "AMP":
                amy.send(synth=p["synth"], bp0=bp_str)
            else:
                amy.send(synth=p["synth"], bp1=bp_str)
        except Exception:
            pass

    def send_midi_msg(self, data):
        try:
            if hasattr(self.input_driver, "uart") and self.input_driver.uart:
                self.input_driver.uart.write(data)
        except Exception:
            pass

    def sequencer_stop(self):
        try:
            import amy
            p = self._preset_values()
            amy.send(synth=p["synth"], vel=0)
            if self.seq_last_note >= 0:
                ch = clamp(int(self.cfg["system"].get("midi_channel", 1)) - 1, 0, 15)
                self.send_midi_msg(bytes([0x80 | ch, self.seq_last_note, 0]))
            self.seq_last_note = -1
            self.seq_gate_active = False
        except Exception:
            pass

    def tick_sequencer(self, now):
        seq = self.cfg.setdefault("sequencer", {})
        if not seq.get("running", False):
            return

        bpm = seq.get("bpm", 120)
        steps = seq.get("steps", 16)
        hits = seq.get("hits", 5)
        rotate = seq.get("rotate", 0)
        mutate_prob = seq.get("mutate", 15)
        scale_idx = seq.get("scale_idx", 0)
        root = seq.get("root", 48)
        octs = seq.get("octaves", 2)
        gate_pct = seq.get("gate", 50)

        should_advance = False

        if bpm > 0:
            step_interval = int(15000.0 / bpm)
            if time.ticks_diff(now, self.seq_last_tick) >= step_interval:
                self.seq_last_tick = now
                should_advance = True
        else:
            try:
                gate_v = amyboard.cv_in(1)
                gate_high = (gate_v >= 2.5)
                if gate_high and not self.seq_ext_clock_prev:
                    should_advance = True
                self.seq_ext_clock_prev = gate_high
            except Exception:
                pass

        if self.seq_gate_active and time.ticks_diff(now, self.seq_gate_off_time) >= 0:
            try:
                import amy
                p = self._preset_values()
                amy.send(synth=p["synth"], vel=0)
                if self.seq_last_note >= 0:
                    ch = clamp(int(self.cfg["system"].get("midi_channel", 1)) - 1, 0, 15)
                    self.send_midi_msg(bytes([0x80 | ch, self.seq_last_note, 0]))
            except Exception:
                pass
            self.seq_gate_active = False

        if should_advance:
            self.seq_step = (self.seq_step + 1) % steps
            raw_euc = generate_euclidean(hits, steps)
            is_hit = raw_euc[(self.seq_step - rotate) % steps]
            
            if is_hit:
                import random
                if random.randint(1, 100) <= mutate_prob:
                    self.seq_turing_reg = (self.seq_turing_reg ^ 1)
                bit0 = (self.seq_turing_reg & 1)
                self.seq_turing_reg = ((self.seq_turing_reg >> 1) | (bit0 << 15)) & 0xFFFF
                
                scale_intervals = SequencerPage.SCALES[scale_idx][1]
                val_8bit = (self.seq_turing_reg & 0xFF)
                degree = val_8bit % len(scale_intervals)
                octave_offset = (val_8bit // len(scale_intervals)) % octs
                note = root + (octave_offset * 12) + scale_intervals[degree]
                note = clamp(note, 0, 127)
                
                try:
                    import amy
                    p = self._preset_values()
                    amy.send(synth=p["synth"], note=note, vel=1.0)
                    ch = clamp(int(self.cfg["system"].get("midi_channel", 1)) - 1, 0, 15)
                    self.send_midi_msg(bytes([0x90 | ch, note, 100]))
                    self.seq_last_note = note
                    self.seq_gate_active = True
                    step_dur = int(15000.0 / bpm) if bpm > 0 else 120
                    self.seq_gate_off_time = time.ticks_add(now, int(step_dur * gate_pct / 100.0))
                except Exception:
                    pass

    def tick_drums(self, now):
        drums = self.cfg.setdefault("drums", {})
        if not drums.get("running", False):
            return
        bpm = drums.get("bpm", 120)
        step_interval = int(15000.0 / bpm)
        if time.ticks_diff(now, self.drum_last_tick) >= step_interval:
            self.drum_last_tick = now
            self.drum_step = (self.drum_step + 1) % 16
            
            tracks = drums.get("tracks", [])
            drum_patches = [0, 1, 2, 3]
            
            for tidx in range(min(4, len(tracks))):
                t = tracks[tidx]
                if t.get("mute", False):
                    continue
                hits = t.get("hits", 4)
                steps = t.get("steps", 16)
                rot = t.get("rotate", 0)
                raw = generate_euclidean(hits, steps)
                step_idx = (self.drum_step - rot) % steps
                if raw[step_idx]:
                    vol = t.get("vol", 80) / 100.0
                    try:
                        import amy
                        amy.send(osc=32 + tidx, wave=amy.PCM, patch=drum_patches[tidx], vel=vol)
                    except Exception:
                        pass

    def tick_lfos(self, now):
        lfos = self.cfg.setdefault("lfos", [])
        if time.ticks_diff(now, self.lfo_last_tick) < 30:
            return
        self.lfo_last_tick = now
        
        now_s = now / 1000.0
        import math
        for idx in range(min(2, len(lfos))):
            lfo = lfos[idx]
            wave = lfo.get("wave", "Sine")
            rate = float(lfo.get("rate", 1.0))
            depth = int(lfo.get("depth", 50)) / 100.0
            dest = lfo.get("dest", "None")
            if dest == "None":
                continue
            
            t = (now_s * rate) % 1.0
            if wave == "Sine":
                val = math.sin(t * 2 * math.pi)
            elif wave == "Triangle":
                val = 4.0 * abs(t - 0.5) - 1.0
            elif wave == "Saw Up":
                val = 2.0 * t - 1.0
            elif wave == "Saw Dn":
                val = 1.0 - 2.0 * t
            elif wave == "Square":
                val = 1.0 if t < 0.5 else -1.0
            else:
                val = math.sin(t * 8.0) * 0.7
            
            mod_v = val * depth
            try:
                import amy
                if dest == "Filter":
                    p = self._preset_values()
                    base_fc = float(p.get("filter_cutoff", 1000))
                    new_fc = clamp(base_fc * (2.0 ** (mod_v * 1.5)), 80, 16000)
                    amy.send(synth=p["synth"], filter_freq=int(new_fc))
                elif dest == "Pitch":
                    p = self._preset_values()
                    amy.send(synth=p["synth"], pitch_bend=mod_v * 0.1)
                elif dest == "PWM":
                    p = self._preset_values()
                    amy.send(synth=p["synth"], duty=clamp(0.5 + mod_v * 0.4, 0.05, 0.95))
            except Exception:
                pass

    def run(self):
        last_save = time.ticks_ms()
        last_render = time.ticks_ms()
        last_gc = time.ticks_ms()
        needs_render = True
        
        while True:
            try:
                import sys, select
                if select.select([sys.stdin], [], [], 0)[0]:
                    ch = sys.stdin.read(1)
                    if ch in ('\x03', '\x04', 'q', 'r', 'x'):
                        print("\n=== REPL BREAK: EXITING MENU LOOP ===\n")
                        break
            except Exception:
                pass

            now = time.ticks_ms()

            # 1. Fast Input Polling
            ev = self.input_driver.poll(now)
            if ev.delta or ev.click or ev.long_press:
                self.handle_event(ev)
                needs_render = True

            # 2. High-Precision Engine Ticks (Sub-millisecond Sequencer & Drums)
            self.tick_sequencer(now)
            self.tick_drums(now)
            self.tick_lfos(now)

            # 3. CV/Gate Input Processing (if Sequencer is not running)
            if not self.cfg.get("sequencer", {}).get("running", False):
                try:
                    p = self._preset_values()
                    pitch_v = amyboard.cv_in(p["cv_pitch_input"])
                    gate_v = amyboard.cv_in(p["cv_gate_input"])
                    note = int(pitch_v * p["cv_pitch_scale"] + p["cv_pitch_offset"])
                    note = max(0, min(127, note))
                    gate_on = float(p.get("cv_gate_on", DEFAULT_CV_GATE_ON))
                    gate_off = float(p.get("cv_gate_off", DEFAULT_CV_GATE_OFF))
                    gate = gate_v >= (gate_off if self._gate_prev else gate_on)
                    import amy
                    if gate and (not self._gate_prev or note != self._last_note):
                        amy.send(synth=p["synth"], note=note, vel=1)
                        self._last_note = note
                    elif (not gate) and self._gate_prev:
                        amy.send(synth=p["synth"], vel=0)
                        self._last_note = -1
                    self._gate_prev = gate
                except Exception:
                    pass

            # 4. Audition Note Release
            if self.audition_off_time and time.ticks_diff(now, self.audition_off_time) >= 0:
                try:
                    import amy
                    p = self._preset_values()
                    amy.send(synth=p["synth"], vel=0)
                except Exception:
                    pass
                self.audition_off_time = None

            # 5. Smart Event-Driven Display Refresh
            is_anim = self.cfg.get("sequencer", {}).get("running", False) or \
                      self.cfg.get("drums", {}).get("running", False) or \
                      self.current_page_key in ("scope", "perform", "lfos")
            render_interval = 40 if is_anim else 150

            if needs_render or time.ticks_diff(now, last_render) >= render_interval:
                self.render()
                last_render = now
                needs_render = False

            # 6. Periodic State Save & Memory Cleanup
            if time.ticks_diff(now, last_save) > 10000:
                self.save_state()
                last_save = now

            if time.ticks_diff(now, last_gc) > 20000:
                try:
                    import gc
                    gc.collect()
                except Exception:
                    pass
                last_gc = now

            # Ultra-short yield
            time.sleep_ms(1)


def main():
    amyboard.init_display()
    app = MenuApp()
    app.run()
