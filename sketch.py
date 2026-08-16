import sys
for p in ("/sd/current", "/user/current", "/current"):
    if p not in sys.path:
        sys.path.insert(0, p)

# --- Minimalist 1-Second Animated Boot Screen ---
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

    # Smooth 1.0-second fluid waveform animation (15 frames x 65ms)
    _num_frames = 15
    for frame in range(_num_frames):
        _d.fill(0)
        
        # Clean typography centered
        _d.text("amyboard", 32, 42, 1)

        # Fluid oscillating audio waveform with organic envelope
        t = frame / (_num_frames - 1)
        envelope = math.sin(t * 3.14159) * 0.4 + 0.6  # Smooth swell & resolve
        center_y = 76
        for x in range(16, 112, 2):
            angle = (x - 16) * 0.16 + frame * 0.55
            amp = int(18 * math.sin(angle) * envelope)
            _d.line(x, center_y - amp, x, center_y + amp, 1)

        _d.show()

        # Check button for safe mode
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

        time.sleep_ms(65)

    if _SAFE_MODE:
        _d.fill(0)
        _d.text("SAFE MODE", 28, 48, 1)
        _d.text("REPL Active", 20, 68, 1)
        _d.show()
        time.sleep_ms(500)

except Exception:
    pass

if not _SAFE_MODE:
    if "menu" in sys.modules:
        del sys.modules["menu"]
    import menu
    menu.main()
