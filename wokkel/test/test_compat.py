# Copyright (c) Twisted Matrix Laboratories.
# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.compat}.
"""

from __future__ import division, absolute_import

from zope.interface import implementer
from twisted.internet import task
from twisted.internet.interfaces import IReactorTime
from twisted.trial import unittest
from twisted.words.protocols.jabber import xmlstream

from wokkel.compat import IQ

@implementer(IReactorTime)
class FakeReactor(object):

    def __init__(self):
        self.clock = task.Clock()
        self.callLater = self.clock.callLater
        self.getDelayedCalls = self.clock.getDelayedCalls



class IQTest(unittest.TestCase):
    """
    Tests for L{IQ}.
    """

    def setUp(self):
        self.reactor = FakeReactor()
        self.clock = self.reactor.clock


    def testRequestTimingOutEventDispatcher(self):
        """
        Test that an iq request with a defined timeout times out.
        """
        from twisted.words.xish import utility
        output = []
        xs = utility.EventDispatcher()
        xs.send = output.append

        self.iq = IQ(xs, reactor=self.reactor)
        self.iq.timeout = 60
        d = self.iq.send()
        self.assertFailure(d, xmlstream.TimeoutError)

        self.clock.pump([1, 60])
        self.assertFalse(self.reactor.getDelayedCalls())
        self.assertFalse(xs.iqDeferreds)
        return d
