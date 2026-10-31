"""Allows running the application with ``python -m querylean``."""

from querylean.app.application import Application

raise SystemExit(Application.run())
