"""
SparkRail AI Block Planning System - Main Entry Point.
"""
import sys
from src.cli import main as cli_main

def main():
    """
    Entry point for SparkRail.
    Delegates to the canonical CLI in src.cli.
    """
    if len(sys.argv) == 1:
        # Default to running the demo if no arguments are provided
        sys.argv.append("demo")
    cli_main()

if __name__ == "__main__":
    main()
