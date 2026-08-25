"""Allow ``python -m pipeline.objects``."""

from pipeline.objects.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
