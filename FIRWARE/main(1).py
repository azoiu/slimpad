# SlimPad firmware — 12 tipk + EC11 encoder
# KMK + CircuitPython
# Clipboard zgodovina: kopiraj → shrani, encoder listaj, klik prilepi

import board
import busio
import displayio
import terminalio
import time
import supervisor
from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC, make_key
from kmk.modules.encoder import EncoderHandler
from kmk.modules.layers import Layers
from kmk.keys import DiodeOrientation
from adafruit_display_text import label
import adafruit_displayio_ssd1306

# ═══════════════════════════════════════════
#  CLIPBOARD ZGODOVINA (RAM, max 5 vnosov)
# ═══════════════════════════════════════════
MAX_CLIP = 5
_clips = [""] * MAX_CLIP
_clip_sel = 0
_clip_n = 0

def clip_push():
    global _clips, _clip_n, _clip_sel
    ts = supervisor.ticks_ms() // 1000
    label = f"Kop.{ts}s"
    _clips = [label] + _clips[:-1]
    _clip_n = min(_clip_n + 1, MAX_CLIP)
    _clip_sel = 0

def clip_selected():
    return _clips[_clip_sel] if _clip_n > 0 else ""

def clip_next():
    global _clip_sel
    if _clip_sel < _clip_n - 1:
        _clip_sel += 1

def clip_prev():
    global _clip_sel
    if _clip_sel > 0:
        _clip_sel -= 1

# ═══════════════════════════════════════════
#  OLED — DEDICIRANI PINI (ne deli s COL/ROW)
#  Poveži OLED SCL in SDA na proste pine XIAO
#  ki NISO v matriki
#  Glede na tvojo shematiko: SDA=D4, SCL=D5
#  AKO sta ta pina prosta (ne v matriki) - 
#  sicer spremeni na D8/D9 ali drug prost pin
# ═══════════════════════════════════════════
displayio.release_displays()

# POMEMBNO: Zamenjaj board.D4/board.D5 s pravimi
# prostimi pini glede na tvojo novo shematiko!
# Prosta pina ki nista v COL/ROW matriki.
# Glede na reviewer komentar morajo biti LOČENI od matrike.
try:
    i2c = busio.I2C(board.D5, board.D4)  # SCL=D5, SDA=D4
    display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)
    display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=32)

    ui = displayio.Group()
    display.show(ui)

    _l1 = label.Label(terminalio.FONT, text="SlimPad", color=0xFFFFFF, x=2, y=5)
    _l2 = label.Label(terminalio.FONT, text="[prazno]", color=0xFFFFFF, x=2, y=15)
    _l3 = label.Label(terminalio.FONT, text="0/0",      color=0xFFFFFF, x=2, y=25)
    ui.append(_l1); ui.append(_l2); ui.append(_l3)
    OLED_OK = True
except Exception as e:
    OLED_OK = False
    print("OLED error:", e)

def oled_update(status=""):
    if not OLED_OK:
        return
    clip = clip_selected()
    preview = (clip[:14] + "..") if len(clip) > 14 else (clip if clip else "[prazno]")
    _l1.text = status if status else "SlimPad"
    _l2.text = f">{preview}"
    _l3.text = f"{_clip_sel+1}/{_clip_n}" if _clip_n > 0 else "0/0"

if OLED_OK:
    oled_update()

# ═══════════════════════════════════════════
#  KEYBOARD — 12 stikal, 3×4 matrika
#
#  Glede na tvojo novo shematiko:
#  3 stolpce (C0, C1, C2) × 4 vrstice (R0, R1, R2, R3)
#  = 12 tipk
#
#  Postavi pravilne pine glede na novo PCB!
#  R0=D0, R1=D1, R2=D2, R3=D3
#  C0=D6, C1=D7, C2=D8
# ═══════════════════════════════════════════
keyboard = KMKKeyboard()

# 3 stolpci × 4 vrstice = 12 tipk
keyboard.col_pins = (board.D6, board.D7, board.D8)   # C0, C1, C2
keyboard.row_pins = (board.D0, board.D1, board.D2, board.D3)  # R0-R3
keyboard.diode_orientation = DiodeOrientation.COL2ROW

layers_mod = Layers()
keyboard.modules.append(layers_mod)

# ═══════════════════════════════════════════
#  ENCODER — EC11E (5 pinov, A+B+SW ločeni)
#  A in B direktno na XIAO pine
#  SW (klik) direktno na XIAO pin (ni v matriki!)
# ═══════════════════════════════════════════
enc = EncoderHandler()
# A=D9, B=D10, SW=None (SW gre direktno kot tipka)
enc.pins = ((board.D9, board.D10, None, False),)
keyboard.modules.append(enc)

# ═══════════════════════════════════════════
#  CUSTOM KEYS
# ═══════════════════════════════════════════
def _do_copy(key, keyboard, *args):
    keyboard.hid_pending = True
    keyboard.keys_pressed.add(KC.LCTL)
    keyboard.keys_pressed.add(KC.C)
    clip_push()
    oled_update("KOPIRANO")
    return False

def _un_copy(key, keyboard, *args):
    keyboard.keys_pressed.discard(KC.LCTL)
    keyboard.keys_pressed.discard(KC.C)
    return False

def _do_paste(key, keyboard, *args):
    keyboard.hid_pending = True
    keyboard.keys_pressed.add(KC.LCTL)
    keyboard.keys_pressed.add(KC.V)
    oled_update(f"PRILEPI {_clip_sel+1}")
    return False

def _un_paste(key, keyboard, *args):
    keyboard.keys_pressed.discard(KC.LCTL)
    keyboard.keys_pressed.discard(KC.V)
    return False

def _do_enc_sw(key, keyboard, *args):
    """Encoder klik = prilepi izbrano"""
    keyboard.hid_pending = True
    keyboard.keys_pressed.add(KC.LCTL)
    keyboard.keys_pressed.add(KC.V)
    oled_update(f"POTRJENO {_clip_sel+1}")
    return False

def _un_enc_sw(key, keyboard, *args):
    keyboard.keys_pressed.discard(KC.LCTL)
    keyboard.keys_pressed.discard(KC.V)
    return False

COPY  = make_key(names=('COPY',),  on_press=_do_copy,   on_release=_un_copy)
PASTE = make_key(names=('PASTE',), on_press=_do_paste,  on_release=_un_paste)
ENCSW = make_key(names=('ENCSW',), on_press=_do_enc_sw, on_release=_un_enc_sw)

# ═══════════════════════════════════════════
#  ENCODER VRTENJE
#  Levo = novejše kopirano
#  Desno = starejše kopirano
# ═══════════════════════════════════════════
def _enc_cw(key, keyboard, *args):
    clip_next(); oled_update(); return False

def _enc_ccw(key, keyboard, *args):
    clip_prev(); oled_update(); return False

ENC_CW  = make_key(names=('ENC_CW',),  on_press=_enc_cw)
ENC_CCW = make_key(names=('ENC_CCW',), on_press=_enc_ccw)

enc.map = [((ENC_CCW,), (ENC_CW,))]

# ═══════════════════════════════════════════
#  KEYMAP — 12 tipk (3 COL × 4 ROW)
#
#  Fizična postavitev:
#  ┌──────────┬──────────┬──────────┐
#  │  COPY    │  PASTE   │  UNDO    │  ROW0
#  ├──────────┼──────────┼──────────┤
#  │  SAVE    │ SAVE AS  │  REDO    │  ROW1
#  ├──────────┼──────────┼──────────┤
#  │  SEL ALL │  CUT     │  FIND    │  ROW2
#  ├──────────┼──────────┼──────────┤
#  │  NEW     │  CLOSE   │  PSCR    │  ROW3
#  └──────────┴──────────┴──────────┘
#
#  Encoder (ločeno od matrike):
#  Vrtenje levo/desno = listaj clipboard
#  Klik = prilepi izbrano
# ═══════════════════════════════════════════
keyboard.keymap = [
    [
        # ROW0
        COPY,                       # C0 - KOPIRAJ + shrani
        PASTE,                      # C1 - PRILEPI izbrano
        KC.LCTL(KC.Z),              # C2 - RAZVELJAVI

        # ROW1
        KC.LCTL(KC.S),              # C0 - SHRANI
        KC.LCTL(KC.LSFT(KC.S)),     # C1 - SHRANI KOT
        KC.LCTL(KC.Y),              # C2 - UVELJAVI

        # ROW2
        KC.LCTL(KC.A),              # C0 - IZBERI VSE
        KC.LCTL(KC.X),              # C1 - IZREŽI
        KC.LCTL(KC.F),              # C2 - NAJDI

        # ROW3
        KC.LCTL(KC.N),              # C0 - NOVA DAT.
        KC.LCTL(KC.W),              # C1 - ZAPRI ZAV.
        KC.PSCR,                    # C2 - SCREENSHOT
    ]
]

# ═══════════════════════════════════════════
#  ENCODER SW DIREKTNO NA PIN (ne v matriki)
#  Če imaš SW pin encoderja vezan na prosti pin
#  XIAO, ga dodaj kot navadno tipko:
# ═══════════════════════════════════════════
# Odkomentiraj in nastavi pravi pin:
# from kmk.scanners import RISING
# enc_sw = digitalio.DigitalInOut(board.D3)
# enc_sw.switch_to_input(pull=digitalio.Pull.UP)

# ═══════════════════════════════════════════
#  ZAGON
# ═══════════════════════════════════════════
if __name__ == '__main__':
    keyboard.go()
