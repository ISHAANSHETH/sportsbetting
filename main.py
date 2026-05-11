#!/usr/bin/env python3
"""
Sports Betting Predictor
Zero API keys required — all data from public sources.

Usage:
  python main.py "Portugal vs Spain Nations League"
  python main.py "Djokovic vs Alcaraz Wimbledon tomorrow"
  python main.py "Jon Jones vs Stipe Miocic UFC"
  python main.py "India vs Australia T20 World Cup"
  python main.py show sports
"""
import sys
import os

# Ensure src is importable
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from src.predictor import run


def main():
    if len(sys.argv) < 2:
        run("help")
        return

    query = " ".join(sys.argv[1:])
    run(query)


if __name__ == "__main__":
    main()
