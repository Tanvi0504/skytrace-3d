"""CLI helper for the transparent, pre-processed SkyTrace backup demo."""

from __future__ import annotations

import argparse
import sys
import webbrowser

from skytrace.demo_check import DEMO_RUN_ID, check_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show or open the clearly labelled pre-processed SkyTrace demo result.")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:8080")
    parser.add_argument("--open", action="store_true", help="Open the demo only after its services pass readiness checks.")
    args = parser.parse_args(argv)
    report = check_demo(args.backend_url, args.frontend_url)
    if report["status"] != "DEMO READY":
        print("DEMO NOT READY. Start the application with `docker compose up --build` and run `python -m skytrace.demo_check` for exact failures.", file=sys.stderr)
        return 1
    url = f"{args.frontend_url.rstrip('/')}/viewer/{DEMO_RUN_ID}"
    print("PRE-PROCESSED DEMO RESULT")
    print(url)
    if args.open:
        webbrowser.open(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
