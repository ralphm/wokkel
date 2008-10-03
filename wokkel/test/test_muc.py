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
        self.test_room = 'test'
        self.test_srv  = 'conference.example.org'
        self.test_nick = 'Nick'

        self.room_jid = JID(self.test_room+'@'+self.test_srv+'/'+self.test_nick)

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
	           
	
        d, self.protocol.receivedUserPresence = calledAsync(userPresence)
        self.stub.send(p)
        return d


    def test_groupChat(self):
        """Test receiving room presence
        """
        m = muc.GroupChat('test@test.com',body='test')
	
        def groupChat(elem):
            self.failUnless(elem.name=='message','Wrong stanza')
            self.failUnless(elem['type'] == 'groupchat', 'Wrong attribute')
            	           
	
        d, self.protocol.receivedGroupChat = calledAsync(groupChat)
        self.stub.send(m)
        return d


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
        

        def cb(room):
            self.assertEquals(self.test_room, room.name)

        d = self.protocol.join(self.test_srv, self.test_room, self.test_nick)
        d.addCallback(cb)

        prs = self.stub.output[-1]
        self.failUnless(prs.name=='presence', "Need to be presence")
        self.failUnless(getattr(prs, 'x', None), 'No muc x element')

        # send back user presence, they joined        
        response = muc.UserPresence(frm=self.test_room+'@'+self.test_srv+'/'+self.test_nick)
        self.stub.send(response)
        return d


    def test_joinRoomForbidden(self):
        """Test joining a room and getting an error
        """

        def cb(error):
            self.failUnless(isinstance(error.value,muc.PresenceError), 'Wrong type')
            self.failUnless(error.value['type']=='error', 'Not an error returned')
            
            
        d = self.protocol.join(self.test_srv, self.test_room, self.test_nick)
        d.addBoth(cb)

        prs = self.stub.output[-1]
        self.failUnless(prs.name=='presence', "Need to be presence")
        self.failUnless(getattr(prs, 'x', None), 'No muc x element')
        # send back user presence, they joined
        
        response = muc.PresenceError(error=muc.MUCError('auth',
                                                        'forbidden'
                                                        ),
                                     frm=self.room_jid.full())
        self.stub.send(response)
        return d        

    def test_partRoom(self):
        self.fail('Not Implemented')
        

    def test_ban(self):
        
        self.fail('Not Implemented')

    def test_kick(self):
        self.fail('Not Implemented')
        

    def test_password(self):
        """Test sending a password via presence to a password protected room.
        """
        
        
        self.fail('Not Implemented')

    def test_history(self):
        
        self.fail('Not Implemented')


    def test_oneToOneChat(self):
        """Test converting a one to one chat
        """
        archive = []
        thread = "e0ffe42b28561960c6b12b944a092794b9683a38"
        # create messages
        msg = domish.Element((None, 'message'))
        msg['to'] = 'testing@example.com'
        msg['type'] = 'chat'
        msg.addElement('body', None, 'test')
        msg.addElement('thread', None, thread)

        archive.append(msg)

        msg = domish.Element((None, 'message'))
        msg['to'] = 'testing2@example.com'
        msg['type'] = 'chat'
        msg.addElement('body', None, 'yo')
        msg.addElement('thread', None, thread)

        archive.append(msg)

        self.protocol.history(self.room_jid.userhost(), archive)


        while len(self.stub.output)>0:
            m = self.stub.output.pop()
            # check for delay element
            self.failUnless(m.name=='message', 'Wrong stanza')
            self.failUnless(xpath.matches("/message/delay", m), 'Invalid history stanza')
        

    def test_invite(self):
        self.fail('Not Implemented')

        
    def test_privateMessage(self):
        
        self.fail('Not Implemented')

    def test_register(self):
        """Test client registering with a room. http://xmpp.org/extensions/xep-0045.html#register

        """
        
        def cb(iq):
            # check for a result
            self.failUnless(iq['type']=='result', 'We did not get a result')
        
        d = self.protocol.register(self.room_jid.userhost())
        d.addCallback(cb)

        iq = self.stub.output[-1]
        
        self.failUnless(xpath.matches("/iq/query[@xmlns='%s']" % (muc.NS_REQUEST), iq), 'Invalid iq register request')
        
        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d

    def test_voice(self):
        """
        """
        self.protocol.voice(self.room_jid.userhost())

        m = self.stub.output[-1]
        
        self.failUnless(xpath.matches("/message/x[@type='submit']/field/value[text()='%s']" % (muc.NS_REQUEST,), m), 'Invalid voice message stanza')


    def test_roomConfigure(self):
        """
        """

        def cb(iq):
            self.failUnless(iq['type']=='result', 'Not a result')
            

        fields = []

        fields.append(data_form.Field(label='Natural-Language Room Name',
                                      var='muc#roomconfig_roomname',
                                      value=self.test_room))
        
        d = self.protocol.configure(self.room_jid.userhost(), fields)
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.failUnless(xpath.matches("/iq/query[@xmlns='%s']/x"% (muc.NS_OWNER,), iq), 'Bad configure request')
        
        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


