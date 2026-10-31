"""Configuration persistence error."""

from __future__ import annotations


class ConfigError(Exception):
    """Raised when the configuration file cannot be written."""
