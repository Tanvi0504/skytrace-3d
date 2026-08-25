"""Allow ``python -m pipeline.georeferencing``."""

from pipeline.georeferencing.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
