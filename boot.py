# boot.py
import sys
for p in ("/user/current", "/current"):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import sketch
except Exception as e:
    print("Error booting sketch:", e)
