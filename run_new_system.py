#!/usr/bin/env python3
"""
Convenience script to run the new save slot system.

Usage:
    python run_new_system.py
    python run_new_system.py --no-llm
    python run_new_system.py --debug
"""

if __name__ == "__main__":
    from dnd_engine.main_v2 import main
    main()
