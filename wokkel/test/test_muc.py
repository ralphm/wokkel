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

        self.user_jid = JID('test@jabber.org/Testing')

    def _createRoom(self):
        # create a room
        self.current_room = muc.Room(self.test_room, self.test_srv, self.test_nick)
        self.protocol._setRoom(self.current_room)


    def test_interface(self):
        """
        Do instances of L{muc.MUCClient} provide L{iwokkel.IMUCClient}?
        """
        verify.verifyObject(iwokkel.IMUCClient, self.protocol)


    def test_userJoinedRoom(self):
        """Test receiving a user joined event.
        """
        p = muc.UserPresence()
	p['to'] = self.user_jid.full()
        p['from'] = self.room_jid.full()

        # create a room
        self._createRoom()

        def userPresence(room, user):
            self.failUnless(room.name==self.test_room, 'Wrong room name')
            self.failUnless(room.inRoster(user), 'User not in roster')
            	           
	
        d, self.protocol.userJoinedRoom = calledAsync(userPresence)
        self.stub.send(p)
        return d


    def test_groupChat(self):
        """Test receiving room presence
        """
        m = muc.GroupChat('test@test.com',body='test')
	m['from'] = self.room_jid.full()

        self._createRoom()

        def groupChat(room, user, message):
            self.failUnless(message=='test', "Wrong group chat message")
            self.failUnless(room.name==self.test_room, 'Wrong room name')
            	           
	
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
        
        def cb(left):
            self.failUnless(left, 'did not leave room')


        d = self.protocol.leave(self.room_jid)
        d.addCallback(cb)

        prs = self.stub.output[-1]
        
        self.failUnless(prs['type']=='unavailable', 'Unavailable is not being sent')
        
        response = prs
        response['from'] = response['to']
        response['to'] = 'test@jabber.org'

        self.stub.send(response)
        return d
        

    def test_ban(self):
        
        banned = JID('ban@jabber.org/TroubleMakger')
        def cb(banned):
            self.failUnless(banned, 'Did not ban user')

            
        d = self.protocol.ban(self.room_jid, banned, self.user_jid, reason='Spam')
        d.addCallback(cb)

        iq = self.stub.output[-1]
        
        self.failUnless(xpath.matches("/iq[@type='set' and @to='%s']/query/item[@affiliation='outcast']" % (self.room_jid.userhost(),), iq), 'Wrong ban stanza')

        response = toResponse(iq, 'result')

        self.stub.send(response)

        return d


    def test_kick(self):

        kicked = JID('kick@jabber.org/TroubleMakger')
        def cb(kicked):
            self.failUnless(kicked, 'Did not kick user')

            
        d = self.protocol.kick(self.room_jid, kicked, self.user_jid, reason='Spam')
        d.addCallback(cb)

        iq = self.stub.output[-1]
        
        self.failUnless(xpath.matches("/iq[@type='set' and @to='%s']/query/item[@affiliation='none']" % (self.room_jid.userhost(),), iq), 'Wrong kick stanza')

        response = toResponse(iq, 'result')

        self.stub.send(response)

        return d

        

    def test_password(self):
        """Test sending a password via presence to a password protected room.
        """
        
        self.protocol.password(self.room_jid, 'secret')
        
        prs = self.stub.output[-1]
        
        self.failUnless(xpath.matches("/presence[@to='%s']/x/password[text()='secret']" % (self.room_jid.full(),), prs), 'Wrong presence stanza')


    def test_history(self):
        """Test receiving history on room join.
        """
        m = muc.HistoryMessage(self.room_jid.userhost(), self.protocol._makeTimeStamp(), body='test')
 	m['from'] = self.room_jid.full()
        
        self._createRoom()

        def roomHistory(room, user, body, stamp, frm=None):
            self.failUnless(body=='test', "wrong message body")
            self.failUnless(stamp, 'Does not have a history stamp')
	           

        d, self.protocol.receivedHistory = calledAsync(roomHistory)
        self.stub.send(m)
        return d


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
        other_jid = 'test@jabber.org'

        self.protocol.invite(other_jid, 'This is a test')

        msg = self.stub.output[-1]

        self.failUnless(xpath.matches("/message[@to='%s']/x/invite/reason" % (other_jid,), msg), 'Wrong message type')


        
    def test_privateMessage(self):
        """Test sending private messages to muc entities.
        """
        other_nick = self.room_jid.userhost()+'/OtherNick'

        self.protocol.chat(other_nick, 'This is a test')

        msg = self.stub.output[-1]

        self.failUnless(xpath.matches("/message[@type='chat' and @to='%s']/body" % (other_nick,), msg), 'Wrong message type')


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


