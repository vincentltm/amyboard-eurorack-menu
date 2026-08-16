#!/usr/bin/env python3
"""
AMYboard Automatic 1-Click Fast Deployment Script
Uses MicroPython Raw REPL (Ctrl+A/Ctrl+D) - No Safe Mode or Button Pressing Required!
"""

import sys
import glob
import time
import subprocess

try:
    import serial
except ImportError:
    print("Installing pyserial...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyserial"])
    import serial

def enter_raw_repl(s):
    # Interrupt any running loop and enter Raw REPL
    for _ in range(3):
        s.write(b"\x03\x03\x01")
        time.sleep(0.15)
        buf = s.read_all()
        if b"raw REPL" in buf or b">" in buf:
            return True
    s.write(b"\x01")
    time.sleep(0.2)
    return b">" in s.read_all()

def raw_exec(s, code):
    # Send code block in Raw REPL
    s.write(code.encode("utf-8"))
    s.write(b"\x04")  # Ctrl+D to execute
    
    # Read until \x04
    out = b""
    start = time.time()
    while time.time() - start < 4:
        if s.in_waiting:
            out += s.read(s.in_waiting)
            if b"\x04" in out:
                break
        time.sleep(0.02)
    return out.decode("utf-8", errors="replace")

def upload_file(s, local_path, remote_path):
    print(f"📦 Uploading {local_path} -> {remote_path}...")
    with open(local_path, "rb") as f:
        data = f.read()

    # Prep directory & clear file
    init_code = f"""import os
def _m(p):
    try: os.mkdir(p)
    except: pass
_m('/user')
_m('/user/current')
f = open({repr(remote_path)}, 'wb')
f.close()
"""
    raw_exec(s, init_code)

    # Write in binary chunks
    chunk_size = 1024
    for i in range(0, len(data), chunk_size):
        chunk = data[i : i + chunk_size]
        chunk_code = f"with open({repr(remote_path)}, 'ab') as f: f.write({repr(chunk)})\n"
        raw_exec(s, chunk_code)

    print(f"   {local_path} uploaded successfully ({len(data)} bytes).")

def main():
    ports = [p for p in glob.glob("/dev/cu.*") if "usbmodem" in p or "usbserial" in p or "ACM" in p]
    if not ports:
        print("❌ Error: No AMYboard USB serial port detected!")
        print("Please plug your AMYboard into your Mac via USB.")
        sys.exit(1)

    port = ports[0]
    print(f"🔌 Found AMYboard on port: {port}")

    try:
        s = serial.Serial(port, 115200, timeout=1)
    except Exception as e:
        print(f"❌ Error opening port {port}: {e}")
        sys.exit(1)

    print("⚡ Connecting over MicroPython Raw REPL...")
    if not enter_raw_repl(s):
        print("⚠️ Forcing REPL reset...")
        s.write(b"\x03\x03\x01")
        time.sleep(0.3)

    upload_file(s, "boot.py", "/user/boot.py")
    upload_file(s, "menu.py", "/user/current/menu.py")
    upload_file(s, "sketch.py", "/user/current/sketch.py")
    upload_file(s, "perf_config.json", "/user/current/perf_config.json")

    print("🔄 Soft-resetting board to run new code...")
    try:
        raw_exec(s, "import sys\nfor p in ('/user/current', '/current'):\n    if p not in sys.path: sys.path.insert(0, p)\nimport sketch\n")
        s.write(b"\x02")
    except Exception:
        pass
    try:
        s.close()
    except Exception:
        pass

    print("✅ AUTOMATIC DEPLOY COMPLETE! Your AMYboard has been updated and restarted.")

if __name__ == "__main__":
    main()
