# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{__init__.__version__} and L{incremental} integration.
"""

from __future__ import division, absolute_import

from twisted.trial import unittest

import wokkel
from wokkel import _version

class InitVersionTest(unittest.TestCase):
    """
    Tests for L{wokkel.__init__.__version__}.
    """

    def test_version(self):
        """
        Package version is present and correct.
        """
        self.assertEqual("18.0.0rc4", wokkel.__version__)


class IncrementalVersionTest(unittest.TestCase):
    """
    Tests for L{incremental} integration.
    """

    def test_version(self):
        """
        Package version is present and correct.
        """
        self.assertEqual("wokkel", _version.__version__.package)
        self.assertEqual("18.0.0rc4", _version.__version__.public())
