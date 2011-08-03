# Copyright (c) 2003-2009 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.muc}
"""

from zope.interface import verify

from twisted.trial import unittest
from twisted.internet import defer
from twisted.words.xish import domish, xpath
from twisted.words.protocols.jabber.jid import JID

from wokkel import data_form, iwokkel, muc
from wokkel.generic import parseXml
from wokkel.test.helpers import XmlStreamStub

from twisted.words.protocols.jabber.xmlstream import toResponse

NS_MUC_ADMIN = 'http://jabber.org/protocol/muc#admin'

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

        self.room_jid = JID(tuple=(self.test_room,
                                   self.test_srv,
                                   self.test_nick))
        self.user_jid = JID('test@jabber.org/Testing')


    def _createRoom(self):
        """
        A helper method to create a test room.
        """
        # create a room
        self.current_room = muc.Room(self.test_room,
                                     self.test_srv,
                                     self.test_nick)
        self.protocol._addRoom(self.current_room)


    def test_interface(self):
        """
        Do instances of L{muc.MUCClient} provide L{iwokkel.IMUCClient}?
        """
        verify.verifyObject(iwokkel.IMUCClient, self.protocol)


    def test_userJoinedRoom(self):
        """
        The client receives presence from an entity joining the room.

        This tests the class L{muc.UserPresence} and the userJoinedRoom event method.

        The test sends the user presence and tests if the event method is called.

        """
        xml = """
            <presence to='%s' from='%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.user_jid.full(), self.room_jid.full())

        # create a room
        self._createRoom()

        def userJoinedRoom(room, user):
            self.assertEquals(self.test_room, room.roomIdentifier,
                              'Wrong room name')
            self.assertTrue(room.inRoster(user), 'User not in roster')

        d, self.protocol.userJoinedRoom = calledAsync(userJoinedRoom)
        self.stub.send(parseXml(xml))
        return d


    def test_groupChat(self):
        """
        The client receives a groupchat message from an entity in the room.
        """
        xml = """
            <message to='test@test.com' from='%s' type='groupchat'>
              <body>test</body>
            </message>
        """ % (self.room_jid.full())

        self._createRoom()

        def groupChat(room, user, message):
            self.assertEquals('test', message, "Wrong group chat message")
            self.assertEquals(self.test_room, room.roomIdentifier,
                              'Wrong room name')

        d, self.protocol.receivedGroupChat = calledAsync(groupChat)
        self.stub.send(parseXml(xml))
        return d


    def test_joinRoom(self):
        """
        Joining a room
        """

        def cb(room):
            self.assertEqual(self.test_room, room.roomIdentifier)

        d = self.protocol.join(self.test_srv, self.test_room, self.test_nick)
        d.addCallback(cb)

        prs = self.stub.output[-1]
        self.assertEquals('presence', prs.name, "Need to be presence")
        self.assertNotIdentical(None, prs.x, 'No muc x element')

        # send back user presence, they joined
        xml = """
            <presence from='%s@%s/%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.test_room, self.test_srv, self.test_nick)
        self.stub.send(parseXml(xml))
        return d


    def test_joinRoomForbidden(self):
        """
        Client joining a room and getting a forbidden error.
        """

        def cb(error):
            self.assertEquals('forbidden', error.value.mucCondition,
                              'Wrong muc condition')

        d = self.protocol.join(self.test_srv, self.test_room, self.test_nick)
        d.addBoth(cb)

        prs = self.stub.output[-1]
        self.assertEquals('presence', prs.name, "Need to be presence")
        self.assertNotIdentical(None, prs.x, 'No muc x element')

        # send back error, forbidden
        xml = """
            <presence from='%s' type='error'>
              <error type='auth'>
                <forbidden xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
              </error>
            </presence>
        """ % (self.room_jid.full())
        self.stub.send(parseXml(xml))
        return d


    def test_joinRoomBadJID(self):
        """
        Client joining a room and getting a jid-malformed error.
        """

        def cb(error):
            self.assertEquals('jid-malformed', error.value.mucCondition,
                              'Wrong muc condition')

        d = self.protocol.join(self.test_srv, self.test_room, self.test_nick)
        d.addBoth(cb)

        prs = self.stub.output[-1]
        self.assertEquals('presence', prs.name, "Need to be presence")
        self.assertNotIdentical(None, prs.x, 'No muc x element')

        # send back error, bad JID
        xml = """
            <presence from='%s' type='error'>
              <error type='modify'>
                <jid-malformed xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
              </error>
            </presence>
        """ % (self.room_jid.full())
        self.stub.send(parseXml(xml))
        return d


    def test_partRoom(self):
        """
        Client leaves a room
        """
        def cb(left):
            self.assertTrue(left, 'did not leave room')

        self._createRoom()
        d = self.protocol.leave(self.room_jid)
        d.addCallback(cb)

        prs = self.stub.output[-1]

        self.assertEquals('unavailable', prs['type'],
                          'Unavailable is not being sent')

        xml = """
            <presence to='test@jabber.org' from='%s' type='unavailable'/>
        """ % (self.room_jid.full())
        self.stub.send(parseXml(xml))
        return d


    def test_userPartsRoom(self):
        """
        An entity leaves the room, a presence of type unavailable is received by the client.
        """

        xml = """
            <presence to='%s' from='%s' type='unavailable'/>
        """ % (self.user_jid.full(), self.room_jid.full())

        # create a room
        self._createRoom()

        # add user to room
        user = muc.User(self.room_jid.resource)
        room = self.protocol._getRoom(self.room_jid)
        room.addUser(user)

        def userPresence(room, user):
            self.assertEquals(self.test_room, room.roomIdentifier,
                              'Wrong room name')
            self.assertFalse(room.inRoster(user), 'User in roster')

        d, self.protocol.userLeftRoom = calledAsync(userPresence)
        self.stub.send(parseXml(xml))
        return d


    def test_ban(self):
        """
        Ban an entity in a room.
        """
        banned = JID('ban@jabber.org/TroubleMaker')

        def cb(banned):
            self.assertTrue(banned, 'Did not ban user')

        d = self.protocol.ban(self.room_jid, banned, reason='Spam',
                              sender=self.user_jid)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        self.assertTrue(xpath.matches(
                "/iq[@type='set' and @to='%s']/query/item"
                    "[@affiliation='outcast']" % (self.room_jid.userhost(),),
                iq),
            'Wrong ban stanza')

        response = toResponse(iq, 'result')
        self.stub.send(response)

        return d


    def test_kick(self):
        """
        Kick an entity from a room.
        """
        nick = 'TroubleMaker'

        def cb(kicked):
            self.assertTrue(kicked, 'Did not kick user')

        d = self.protocol.kick(self.room_jid, nick, reason='Spam',
                               sender=self.user_jid)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        self.assertTrue(xpath.matches(
                "/iq[@type='set' and @to='%s']/query/item"
                    "[@affiliation='none']" % (self.room_jid.userhost(),),
                iq),
            'Wrong kick stanza')

        response = toResponse(iq, 'result')
        self.stub.send(response)

        return d


    def test_password(self):
        """
        Sending a password via presence to a password protected room.
        """

        self.protocol.password(self.room_jid, 'secret')

        prs = self.stub.output[-1]

        self.assertTrue(xpath.matches(
                "/presence[@to='%s']/x/password"
                    "[text()='secret']" % (self.room_jid.full(),),
                prs),
            'Wrong presence stanza')


    def test_historyReceived(self):
        """
        Receiving history on room join.
        """
        xml = """
            <message to='test@test.com' from='%s' type='groupchat'>
              <body>test</body>
              <delay xmlns='urn:xmpp:delay' stamp="2002-10-13T23:58:37Z"
                                            from="%s"/>
            </message>
        """ % (self.room_jid.full(), self.user_jid.full())

        self._createRoom()


        def historyReceived(room, user, body, stamp, frm=None):
            self.assertTrue(body=='test', "wrong message body")
            self.assertTrue(stamp, 'Does not have a history stamp')

        d, self.protocol.receivedHistory = calledAsync(historyReceived)
        self.stub.send(parseXml(xml))
        return d


    def test_oneToOneChat(self):
        """
        Converting a one to one chat to a multi-user chat.
        """
        archive = []
        thread = "e0ffe42b28561960c6b12b944a092794b9683a38"
        # create messages
        msg = domish.Element((None, 'message'))
        msg['to'] = 'testing@example.com'
        msg['type'] = 'chat'
        msg.addElement('body', None, 'test')
        msg.addElement('thread', None, thread)

        archive.append({'stanza': msg, 'timestamp': '2002-10-13T23:58:37Z'})

        msg = domish.Element((None, 'message'))
        msg['to'] = 'testing2@example.com'
        msg['type'] = 'chat'
        msg.addElement('body', None, 'yo')
        msg.addElement('thread', None, thread)

        archive.append({'stanza': msg, 'timestamp': '2002-10-13T23:58:43Z'})

        self.protocol.history(self.room_jid, archive)


        while len(self.stub.output)>0:
            m = self.stub.output.pop()
            # check for delay element
            self.assertTrue(m.name=='message', 'Wrong stanza')
            self.assertTrue(xpath.matches("/message/delay", m), 'Invalid history stanza')


    def test_invite(self):
        """
        Invite a user to a room
        """
        bareRoomJID = self.room_jid.userhostJID()
        invitee = JID('test@jabber.org')

        self.protocol.invite(bareRoomJID, 'This is a test', invitee)

        msg = self.stub.output[-1]

        query = u"/message[@to='%s']/x/invite/reason" % bareRoomJID
        self.assertTrue(xpath.matches(query, msg), 'Wrong message type')


    def test_privateMessage(self):
        """
        Send private messages to muc entities.
        """
        other_nick = self.room_jid.userhost()+'/OtherNick'

        self.protocol.chat(other_nick, 'This is a test')

        msg = self.stub.output[-1]

        query = "/message[@type='chat' and @to='%s']/body" % other_nick
        self.assertTrue(xpath.matches(query, msg), 'Wrong message type')


    def test_register(self):
        """
        Client registering with a room.

        http://xmpp.org/extensions/xep-0045.html#register
        """

        def cb(iq):
            # check for a result
            self.assertTrue(iq['type']=='result', 'We did not get a result')

        d = self.protocol.register(self.room_jid)
        d.addCallback(cb)

        iq = self.stub.output[-1]
        query = "/iq/query[@xmlns='%s']" % muc.NS_REQUEST
        self.assertTrue(xpath.matches(query, iq), 'Invalid iq register request')

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_voice(self):
        """
        Client requesting voice for a room.
        """
        self.protocol.voice(self.room_jid)

        m = self.stub.output[-1]

        query = ("/message/x[@type='submit']/field/value"
                    "[text()='%s']") % muc.NS_MUC_REQUEST
        self.assertTrue(xpath.matches(query, m), 'Invalid voice message stanza')


    def test_roomConfigure(self):
        """
        Default configure and changing the room name.
        """

        def cb(iq):
            self.assertTrue(iq['type']=='result', 'Not a result')


        fields = []

        fields.append(data_form.Field(label='Natural-Language Room Name',
                                      var='muc#roomconfig_roomname',
                                      value=self.test_room))

        d = self.protocol.configure(self.room_jid.userhost(), fields)
        d.addCallback(cb)

        iq = self.stub.output[-1]
        query = "/iq/query[@xmlns='%s']/x"% muc.NS_MUC_OWNER
        self.assertTrue(xpath.matches(query, iq), 'Bad configure request')

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_roomDestroy(self):
        """
        Destroy a room.
        """

        def cb(destroyed):
            self.assertTrue(destroyed==True, 'Room not destroyed.')

        d = self.protocol.destroy(self.room_jid)
        d.addCallback(cb)

        iq = self.stub.output[-1]
        query = "/iq/query[@xmlns='%s']/destroy"% muc.NS_MUC_OWNER
        self.assertTrue(xpath.matches(query, iq), 'Bad configure request')

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_nickChange(self):
        """
        Send a nick change to the server.
        """
        test_nick = 'newNick'

        self._createRoom()

        def cb(room):
            self.assertEquals(self.test_room, room.roomIdentifier)
            self.assertEquals(test_nick, room.nick)

        d = self.protocol.nick(self.room_jid, test_nick)
        d.addCallback(cb)

        prs = self.stub.output[-1]
        self.assertEquals('presence', prs.name, "Need to be presence")
        self.assertNotIdentical(None, prs.x, 'No muc x element')

        # send back user presence, nick changed
        xml = """
            <presence from='%s@%s/%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.test_room, self.test_srv, test_nick)
        self.stub.send(parseXml(xml))
        return d


    def test_grantVoice(self):
        """
        Test granting voice to a user.

        """
        nick = 'TroubleMaker'
        def cb(give_voice):
            self.assertTrue(give_voice, 'Did not give voice user')

        d = self.protocol.grantVoice(self.room_jid, nick, sender=self.user_jid)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        query = ("/iq[@type='set' and @to='%s']/query/item"
                     "[@role='participant']") % self.room_jid.userhost()
        self.assertTrue(xpath.matches(query, iq), 'Wrong voice stanza')

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_changeStatus(self):
        """
        Change status
        """
        self._createRoom()
        room = self.protocol._getRoom(self.room_jid)
        user = muc.User(self.room_jid.resource)
        room.addUser(user)

        def cb(room):
            self.assertEqual(self.test_room, room.roomIdentifier)
            user = room.getUser(self.room_jid.resource)
            self.assertNotIdentical(None, user, 'User not found')
            self.assertEqual('testing MUC', user.status, 'Wrong status')
            self.assertEqual('xa', user.show, 'Wrong show')

        d = self.protocol.status(self.room_jid, 'xa', 'testing MUC')
        d.addCallback(cb)

        prs = self.stub.output[-1]

        self.assertEqual('presence', prs.name, "Need to be presence")
        self.assertTrue(getattr(prs, 'x', None), 'No muc x element')

        # send back user presence, status changed
        xml = """
            <presence from='%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
              <show>xa</show>
              <status>testing MUC</status>
            </presence>
        """ % self.room_jid.full()
        self.stub.send(parseXml(xml))
        return d


    def test_getMemberList(self):
        def cb(room):
            members = room.members
            self.assertEqual(1, len(members))
            user = members[0]
            self.assertEqual(JID(u'hag66@shakespeare.lit'), user.entity)
            self.assertEqual(u'thirdwitch', user.nick)
            self.assertEqual(u'participant', user.role)

        self._createRoom()
        bareRoomJID = self.room_jid.userhostJID()
        d = self.protocol.getMemberList(bareRoomJID)
        d.addCallback(cb)

        iq = self.stub.output[-1]
        query = iq.query
        self.assertNotIdentical(None, query)
        self.assertEqual(NS_MUC_ADMIN, query.uri)

        response = toResponse(iq, 'result')
        query = response.addElement((NS_MUC_ADMIN, 'query'))
        item = query.addElement('item')
        item['affiliation'] ='member'
        item['jid'] = 'hag66@shakespeare.lit'
        item['nick'] = 'thirdwitch'
        item['role'] = 'participant'
        self.stub.send(response)

        return d


