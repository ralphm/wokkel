# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.iwokkel}
"""

from twisted.trial import unittest

class DeprecationTest(unittest.TestCase):
    """
    Deprecation test for L{wokkel.subprotocols}.
    """

    def lookForDeprecationWarning(self, testmethod, attributeName, newName):
        """
        Importing C{testmethod} emits a deprecation warning.
        """
        warningsShown = self.flushWarnings([testmethod])
        self.assertEqual(len(warningsShown), 1)
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            "wokkel.iwokkel." + attributeName + " "
            "was deprecated in Wokkel 0.7.0: Use " + newName + " instead.")


    def test_iXMPPHandler(self):
        """
        L{wokkel.iwokkel.IXMPPHandler} is deprecated.
        """
        from wokkel.iwokkel import IXMPPHandler
        IXMPPHandler
        self.lookForDeprecationWarning(
                self.test_iXMPPHandler,
                "IXMPPHandler",
                "twisted.words.protocols.jabber.ijabber."
                    "IXMPPHandler")


    def test_iXMPPHandlerCollection(self):
        """
        L{wokkel.iwokkel.IXMPPHandlerCollection} is deprecated.
        """
        from wokkel.iwokkel import IXMPPHandlerCollection
        IXMPPHandlerCollection
        self.lookForDeprecationWarning(
                self.test_iXMPPHandlerCollection,
                "IXMPPHandlerCollection",
                "twisted.words.protocols.jabber.ijabber."
                    "IXMPPHandlerCollection")
