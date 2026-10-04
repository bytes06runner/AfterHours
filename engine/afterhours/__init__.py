"""Afterhours: an ML risk-curated lending vault for Robinhood Stock Tokens."""

from afterhours import logsafe

__version__ = "0.1.0"

logsafe.install()  # no RPC key or bot token in any log line, from every entry point
