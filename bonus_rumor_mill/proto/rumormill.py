"""Rumor Mill, Milestone 1: the AI Dungeon Master in text.

    python rumormill.py         play
    python rumormill.py --dm    instructor mode: F2 opens the DM view
"""
import argparse
import sys

from rm.ui import RumorMill


def main():
    ap = argparse.ArgumentParser(description="Rumor Mill, Milestone 1")
    ap.add_argument("--dm", action="store_true", help="instructor mode: F2 opens the DM view")
    args = ap.parse_args()
    app = RumorMill(dm=args.dm)
    try:
        app.run()
    finally:
        app.server.stop()


if __name__ == "__main__":
    sys.exit(main())
