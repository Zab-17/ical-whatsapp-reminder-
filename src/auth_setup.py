"""Interactive login setup. Run once to cache session cookies.

Usage:
    python -m src.auth_setup
"""
from src.auth import setup_interactive

if __name__ == "__main__":
    setup_interactive()
