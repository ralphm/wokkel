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

from wokkel import data_form, iwokkel, muc, shim, disco
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



    def test_discoServerSupport(self):
        """Test for disco support from a server.
        """
        test_srv = 'shakespeare.lit'

        def cb(query):
            # check namespace
            self.failUnless(query.uri==disco.NS_INFO, 'Wrong namespace')
            

        d = self.protocol.disco(test_srv)
        d.addCallback(cb)

        iq = self.stub.output[-1]
        
        # send back a response
        response = toResponse(iq, 'result')
        response.addElement('query', disco.NS_INFO)
        # need to add information to response
        response.query.addChild(disco.DiscoFeature(muc.NS))
        response.query.addChild(disco.DiscoIdentity(category='conference',
                                                    name='Macbeth Chat Service',
                                                    type='text'))
        
        self.stub.send(response)
        return d
        

        
    def test_joinRoom(self):
        """Test joining a room
        """
        test_room = 'test'
        test_srv  = 'conference.example.org'
        test_nick = 'Nick'

        def cb(room):
            self.assertEquals(test_room, room.name)

        d = self.protocol.join(test_srv, test_room, test_nick)
        d.addCallback(cb)

        prs = self.stub.output[-1]
        self.failUnless(prs.name=='presence', "Need to be presence")
        self.failUnless(getattr(prs, 'x', None), 'No muc x element')

        # send back user presence, they joined        
        response = muc.UserPresence(frm=test_room+'@'+test_srv+'/'+test_nick)
        self.stub.send(response)
        return d


    def test_joinRoomForbidden(self):
        """Test joining a room and getting an error
        """
        test_room = 'test'
        test_srv  = 'conference.example.org'
        test_nick = 'Nick'

        # p = muc.BasicPresenc(to=)

        def cb(error):
            self.failUnless(isinstance(error.value,muc.PresenceError), 'Wrong type')
            self.failUnless(error.value['type']=='error', 'Not an error returned')
            
            
        d = self.protocol.join(test_srv, test_room, test_nick)
        d.addBoth(cb)

        prs = self.stub.output[-1]
        self.failUnless(prs.name=='presence', "Need to be presence")
        self.failUnless(getattr(prs, 'x', None), 'No muc x element')
        # send back user presence, they joined
        
        response = muc.PresenceError(error=muc.MUCError('auth',
                                                        'forbidden'
                                                        ),
                                     frm=test_room+'@'+test_srv+'/'+test_nick)
        self.stub.send(response)
        return d        
