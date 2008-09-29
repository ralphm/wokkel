# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.muc}
"""

from zope.interface import verify

from twisted.trial import unittest
from twisted.internet import defer
from twisted.words.xish import domish, xpath
from twisted.words.protocols.jabber import error
from twisted.words.protocols.jabber.jid import JID

from wokkel import data_form, iwokkel, muc, shim
from wokkel.generic import parseXml
from wokkel.test.helpers import XmlStreamStub

try:
    from twisted.words.protocols.jabber.xmlstream import toResponse
except ImportError:
    from wokkel.compat import toResponse


def calledAsync(fn):
    """
    Function wrapper that fires a deferred upon calling the given function.
    """
    d = defer.Deferred()

    def func(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
        except:
            d.errback()
        else:
            d.callback(result)

    return d, func


class MucClientTest(unittest.TestCase):
    timeout = 2

    def setUp(self):
        self.stub = XmlStreamStub()
        self.protocol = muc.MUCClient()
        self.protocol.xmlstream = self.stub.xmlstream
        self.protocol.connectionInitialized()


    def test_interface(self):
        """
        Do instances of L{muc.MUCClient} provide L{iwokkel.IMUCClient}?
        """
        verify.verifyObject(iwokkel.IMUCClient, self.protocol)


    def test_presence(self):
        """Test receiving room presence 
        """
        p = muc.UserPresence()

        def userPresence(prs):
            self.failUnless(len(prs.children)==1, 'Not enough children')
            self.failUnless(getattr(prs,'x',None), 'No x element')
            

        d, self.protocol.userPresence = calledAsync(userPresence)
        self.stub.send(p)
        return d

    def test_joinRoom(self):
        """Test joining a room
        """
        test_room = 'test'
        test_srv  = 'conference.example.org'
        test_nick = 'Nick'

        # p = muc.BasicPresenc(to=)

        def cb(room):
            self.assertEquals(test_room, room.name)

        d = self.protocol.joinRoom(test_srv, test_room, test_nick)
        d.addCallback(cb)

        prs = self.stub.output[-1]
        self.failUnless(prs.name=='presence', "Need to be presence")
        self.failUnless(getattr(prs, 'x', None), 'No muc x element')
        # send back user presence, they joined
        
        response = muc.UserPresence()
        print response.toXml()
        self.stub.send(response)
        return d

class MucServiceTest(unittest.TestCase):
    """
    Tests for L{muc.MUCService}.
    """

    def setUp(self):
        self.service = muc.MUCService()

    def handleRequest(self, xml):
        """
        Find a handler and call it directly
        """
        handler = None
        iq = parseXml(xml)
        for queryString, method in self.service.iqHandlers.iteritems():
            if xpath.internQuery(queryString).matches(iq):
                handler = getattr(self.service, method)

        if handler:
            d = defer.maybeDeferred(handler, iq)
        else:
            d = defer.fail(NotImplementedError())

        return d


    def test_interface(self):
        """
        Do instances of L{muc.MucService} provide L{iwokkel.IMucService}?
        """
        verify.verifyObject(iwokkel.IMUCService, self.service)


