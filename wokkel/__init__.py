# Copyright (c) Ralph Meijer.
# See LICENSE for details

"""
Wokkel.

Support library for Twisted applications using XMPP protocols.
"""

from wokkel._version import __version__ as _incremental_version

__version__ = _incremental_version.public()

__all__ = ["__version__"]
