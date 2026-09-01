from __future__ import annotations

import argparse
import json

from .data import load_transactions, profile
from .pipeline import run, write_result


def main() -> None:
    parser = argparse.ArgumentParser(description="BasketLab market-basket research CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--output", default="artifacts/demo.json")
    execute = sub.add_parser("run")
    execute.add_argument("--input", required=True)
    execute.add_argument("--output", default="artifacts/latest.json")
    execute.add_argument("--search-budget", type=int, default=18)
    prof = sub.add_parser("profile")
    prof.add_argument("--input", required=True)
    args = parser.parse_args()
    if args.command == "profile":
        print(json.dumps(profile(load_transactions(args.input)).__dict__, indent=2))
    else:
        write_result(run(None if args.command == "demo" else args.input, args.search_budget if args.command == "run" else 8), args.output)
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()

