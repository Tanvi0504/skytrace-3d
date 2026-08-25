"""Allow ``python -m pipeline.evaluation``."""

from pipeline.evaluation.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
