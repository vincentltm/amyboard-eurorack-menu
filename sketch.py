import sys
for p in ("/sd/current", "/user/current", "/current"):
    if p not in sys.path:
        sys.path.insert(0, p)

# --- Fast Animated Boot Screen with Safe Mode Check ---
_SAFE_MODE = False
try:
    import time
    import math
    import amyboard
    import sh1107

    _i2c = amyboard.get_i2c()
    _d = sh1107.SH1107_I2C(128, 128, _i2c, address=0x3C, rotate=90)

    # Detect Seesaw encoder
    _SS_ADDR = None
    for _a in (0x36, 0x37, 0x49):
        if _a in _i2c.scan():
            _SS_ADDR = _a
            break

    _PIN = 24
    _MASK = 1 << _PIN
    if _SS_ADDR:
        try:
            _i2c.writeto(_SS_ADDR, bytes([0x01, 0x03]) + (int(_MASK)).to_bytes(4, "big"))
            _i2c.writeto(_SS_ADDR, bytes([0x01, 0x0B]) + (int(_MASK)).to_bytes(4, "big"))
            _i2c.writeto(_SS_ADDR, bytes([0x01, 0x05]) + (int(_MASK)).to_bytes(4, "big"))
        except Exception:
            pass

    # Sleek 450ms dynamic waveform boot animation
    _num_frames = 6
    for frame in range(_num_frames):
        _d.fill(0)
        
        # Outer decorative frame
        _d.rect(2, 2, 124, 124, 1)
        _d.rect(4, 4, 120, 120, 1)
        
        # Title Banner
        _d.fill_rect(8, 14, 112, 20, 1)
        _d.text(" A M Y B O A R D ", 10, 20, 0)
        _d.text("EURORACK SYNTH", 12, 40, 1)

        # Dynamic Audio Waveform Animation
        t = frame / (_num_frames - 1)
        center_y = 74
        for x in range(16, 112, 3):
            angle = (x - 16) * 0.12 + frame * 0.8
            amp = int(14 * math.sin(angle) * (0.3 + 0.7 * t))
            _d.line(x, center_y - amp, x, center_y + amp, 1)

        # Progress bar
        _d.rect(16, 100, 96, 6, 1)
        bar_w = int(92 * (frame + 1) / _num_frames)
        _d.fill_rect(18, 102, bar_w, 2, 1)

        _d.show()

        # Check button during animation
        if _SS_ADDR:
            try:
                _i2c.writeto(_SS_ADDR, bytes([0x01, 0x04]))
                time.sleep_ms(2)
                _bulk = int.from_bytes(_i2c.readfrom(_SS_ADDR, 4), "big")
                if (_bulk & _MASK) == 0:  # Pressed
                    _SAFE_MODE = True
                    break
            except Exception:
                pass

        time.sleep_ms(70)

    if _SAFE_MODE:
        _d.fill(0)
        _d.rect(4, 4, 120, 120, 1)
        _d.text("[ SAFE MODE ]", 16, 30, 1)
        _d.text("Menu bypassed", 12, 55, 1)
        _d.text("REPL Active", 20, 75, 1)
        _d.show()
        time.sleep_ms(600)

except Exception:
    pass

if not _SAFE_MODE:
    if "menu" in sys.modules:
        del sys.modules["menu"]
    import menu
    menu.main()
