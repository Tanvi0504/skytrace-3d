"""Allow ``python -m pipeline.analysis``."""

from pipeline.analysis.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
