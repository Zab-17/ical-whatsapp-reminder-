"""Export cached cookies as a base64 string for cloud deployment.

Usage:
    python -m src.export_cookies

Copy the output and set it as the CANVAS_COOKIES_B64 env var on Render.
"""
import base64
import sys
from pathlib import Path

COOKIES_FILE = Path("canvas_cookies.json")


def export():
    if not COOKIES_FILE.exists():
        print("No cookies found. Run 'python -m src.auth_setup' first.")
        sys.exit(1)

    data = COOKIES_FILE.read_bytes()
    encoded = base64.b64encode(data).decode()
    print("\n✅ Copy this entire string and set it as CANVAS_COOKIES_B64 on Render:\n")
    print(encoded)
    print(f"\n(Length: {len(encoded)} chars)")


if __name__ == "__main__":
    export()
