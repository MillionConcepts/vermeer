import argparse
import sys
from pathlib import Path
from orchestrator import execute_pipeline

def main(argv=None):
    parser = argparse.ArgumentParser(prog="vermeer")
    parser.add_argument("run_type", choices=["validate", "run"])
    parser.add_argument("config_file", type=Path)
    args = parser.parse_args(argv)
    return execute_pipeline(args.run_type, args.config_file)


if __name__ == "__main__":
    sys.exit(main())