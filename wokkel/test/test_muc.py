# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.muc}
"""

from __future__ import division, absolute_import

from datetime import datetime
from dateutil.tz import tzutc

from zope.interface import verify

from twisted.trial import unittest
from twisted.internet import defer, task
from twisted.python.compat import iteritems, unicode
from twisted.words.xish import domish, xpath
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.error import StanzaError
from twisted.words.protocols.jabber.xmlstream import TimeoutError, toResponse

from wokkel import data_form, delay, iwokkel, muc
from wokkel.generic import parseXml
from wokkel.test.helpers import TestableStreamManager


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



class StatusCodeTest(unittest.TestCase):
    """
    Tests for L{muc.STATUS_CODE}.
    """

    def test_lookupByValue(self):
        """
        The registered MUC status codes map to STATUS_CODE value constants.

        Note: the identifiers used in the dictionary of status codes are
        borrowed from U{XEP-0306<http://xmpp.org/extensions/xep-0306.html>}
        that defines Extensible Status Conditions for Multi-User Chat. If this
        specification is implemented itself, the dictionary could move there.
        """
        codes = {
            100: 'realjid-public',
            101: 'affiliation-changed',
            102: 'unavailable-shown',
            103: 'unavailable-not-shown',
            104: 'configuration-changed',
            110: 'self-presence',
            170: 'logging-enabled',
            171: 'logging-disabled',
            172: 'non-anonymous',
            173: 'semi-anonymous',
            174: 'fully-anonymous',
            201: 'room-created',
            210: 'nick-assigned',
            301: 'banned',
            303: 'new-nick',
            307: 'kicked',
            321: 'removed-affiliation',
            322: 'removed-membership',
            332: 'removed-shutdown',
        }

        for code, condition in iteritems(codes):
            constantName = condition.replace('-', '_').upper()
            self.assertEqual(getattr(muc.STATUS_CODE, constantName),
                             muc.STATUS_CODE.lookupByValue(code))



class StatusesTest(unittest.TestCase):
    """
    Tests for L{muc.Statuses}.
    """

    def setUp(self):
        self.mucStatuses = muc.Statuses()
        self.mucStatuses.add(muc.STATUS_CODE.SELF_PRESENCE)
        self.mucStatuses.add(muc.STATUS_CODE.ROOM_CREATED)


    def test_interface(self):
        """
        Instances of L{Statuses} provide L{iwokkel.IMUCStatuses}.
        """
        verify.verifyObject(iwokkel.IMUCStatuses, self.mucStatuses)


    def test_contains(self):
        """
        The status contained are 'in' the container.
        """
        self.assertIn(muc.STATUS_CODE.SELF_PRESENCE, self.mucStatuses)
        self.assertIn(muc.STATUS_CODE.ROOM_CREATED, self.mucStatuses)
        self.assertNotIn(muc.STATUS_CODE.NON_ANONYMOUS, self.mucStatuses)


    def test_iter(self):
        """
        All statuses can be iterated over.
        """
        statuses = set()
        for status in self.mucStatuses:
            statuses.add(status)

        self.assertEqual(set([muc.STATUS_CODE.SELF_PRESENCE,
                              muc.STATUS_CODE.ROOM_CREATED]), statuses)


    def test_len(self):
        """
        The number of items in this container is returned by C{__len__}.
        """
        self.assertEqual(2, len(self.mucStatuses))



class GroupChatTest(unittest.TestCase):
    """
    Tests for L{muc.GroupChat}.
    """


    def test_toElementDelay(self):
        """
        If the delay attribute is set, toElement has it rendered.
        """
        message = muc.GroupChat()
        message.delay = delay.Delay(stamp=datetime(2002, 10, 13, 23, 58, 37,
                                                   tzinfo=tzutc()))

        element = message.toElement()

        query = "/message/delay[@xmlns='%s']" % (delay.NS_DELAY,)
        nodes = xpath.queryForNodes(query, element)
        self.assertNotIdentical(None, nodes, "Missing delay element")


    def test_toElementDelayLegacy(self):
        """
        If legacy delay is requested, the legacy format is rendered.
        """
        message = muc.GroupChat()
        message.delay = delay.Delay(stamp=datetime(2002, 10, 13, 23, 58, 37,
                                                   tzinfo=tzutc()))

        element = message.toElement(legacyDelay=True)

        query = "/message/x[@xmlns='%s']" % (delay.NS_JABBER_DELAY,)
        nodes = xpath.queryForNodes(query, element)
        self.assertNotIdentical(None, nodes, "Missing legacy delay element")



class HistoryOptionsTest(unittest.TestCase):
    """
    Tests for L{muc.HistoryOptionsTest}.
    """

    def test_toElement(self):
        """
        toElement renders the history element in the right namespace.
        """
        history = muc.HistoryOptions()

        element = history.toElement()

        self.assertEqual(muc.NS_MUC, element.uri)
        self.assertEqual('history', element.name)


    def test_toElementMaxStanzas(self):
        """
        If C{maxStanzas} is set, the element has the attribute C{'maxstanzas'}.
        """
        history = muc.HistoryOptions(maxStanzas=10)

        element = history.toElement()

        self.assertEqual(u'10', element.getAttribute('maxstanzas'))


    def test_toElementSince(self):
        """
        If C{since} is set, the attribute C{'since'} has a rendered timestamp.
        """
        history = muc.HistoryOptions(since=datetime(2002, 10, 13, 23, 58, 37,
                                                   tzinfo=tzutc()))

        element = history.toElement()

        self.assertEqual(u'2002-10-13T23:58:37Z',
                         element.getAttribute('since'))



class UserPresenceTest(unittest.TestCase):
    """
    Tests for L{muc.UserPresence}.
    """

    def test_fromElementNoUserElement(self):
        """
        Without user element, all associated attributes are None.
        """
        xml = """
            <presence from='coven@chat.shakespeare.lit/thirdwitch'
                      id='026B3509-2CCE-4D69-96D6-25F41FFDC408'
                      to='hag66@shakespeare.lit/pda'>
            </presence>
        """

        element = parseXml(xml)
        presence = muc.UserPresence.fromElement(element)

        self.assertIdentical(None, presence.affiliation)
        self.assertIdentical(None, presence.role)
        self.assertIdentical(None, presence.entity)
        self.assertIdentical(None, presence.nick)
        self.assertEqual(0, len(presence.mucStatuses))


    def test_fromElementUnknownChild(self):
        """
        Unknown child elements are ignored.
        """
        xml = """
            <presence from='coven@chat.shakespeare.lit/thirdwitch'
                      id='026B3509-2CCE-4D69-96D6-25F41FFDC408'
                      to='hag66@shakespeare.lit/pda'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <status xmlns='myns' code='110'/>
              </x>
            </presence>
        """

        element = parseXml(xml)
        presence = muc.UserPresence.fromElement(element)

        self.assertEqual(0, len(presence.mucStatuses))


    def test_fromElementStatusOne(self):
        """
        Status codes are extracted.
        """
        xml = """
            <presence from='coven@chat.shakespeare.lit/thirdwitch'
                      id='026B3509-2CCE-4D69-96D6-25F41FFDC408'
                      to='hag66@shakespeare.lit/pda'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
                <status code='110'/>
              </x>
            </presence>
        """

        element = parseXml(xml)
        presence = muc.UserPresence.fromElement(element)

        self.assertIn(muc.STATUS_CODE.SELF_PRESENCE, presence.mucStatuses)


    def test_fromElementStatusMultiple(self):
        """
        Multiple status codes are all extracted.
        """
        xml = """
            <presence from='coven@chat.shakespeare.lit/thirdwitch'
                      id='026B3509-2CCE-4D69-96D6-25F41FFDC408'
                      to='hag66@shakespeare.lit/pda'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
                <status code='100'/>
                <status code='110'/>
              </x>
            </presence>
        """

        element = parseXml(xml)
        presence = muc.UserPresence.fromElement(element)

        self.assertIn(muc.STATUS_CODE.SELF_PRESENCE, presence.mucStatuses)
        self.assertIn(muc.STATUS_CODE.REALJID_PUBLIC, presence.mucStatuses)


    def test_fromElementStatusEmpty(self):
        """
        Empty status elements are ignored.
        """
        xml = """
            <presence from='coven@chat.shakespeare.lit/thirdwitch'
                      id='026B3509-2CCE-4D69-96D6-25F41FFDC408'
                      to='hag66@shakespeare.lit/pda'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
                <status/>
              </x>
            </presence>
        """

        element = parseXml(xml)
        presence = muc.UserPresence.fromElement(element)

        self.assertEqual(0, len(presence.mucStatuses))


    def test_fromElementStatusBad(self):
        """
        Bad status codes are ignored.
        """
        xml = """
            <presence from='coven@chat.shakespeare.lit/thirdwitch'
                      id='026B3509-2CCE-4D69-96D6-25F41FFDC408'
                      to='hag66@shakespeare.lit/pda'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
                <status code="badvalue"/>
              </x>
            </presence>
        """

        element = parseXml(xml)
        presence = muc.UserPresence.fromElement(element)

        self.assertEqual(0, len(presence.mucStatuses))


    def test_fromElementStatusUnknown(self):
        """
        Unknown status codes are not recorded in C{mucStatuses}.
        """
        xml = """
            <presence from='coven@chat.shakespeare.lit/thirdwitch'
                      id='026B3509-2CCE-4D69-96D6-25F41FFDC408'
                      to='hag66@shakespeare.lit/pda'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
                <status code="999"/>
              </x>
            </presence>
        """

        element = parseXml(xml)
        presence = muc.UserPresence.fromElement(element)

        self.assertEqual(0, len(presence.mucStatuses))


    def test_fromElementItem(self):
        """
        Item attributes are parsed properly.
        """
        xml = """
            <presence from='coven@chat.shakespeare.lit/thirdwitch'
                      to='crone1@shakespeare.lit/desktop'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member'
                      jid='hag66@shakespeare.lit/pda'
                      role='participant'
                      nick='thirdwitch'/>
              </x>
            </presence>
        """

        element = parseXml(xml)
        presence = muc.UserPresence.fromElement(element)
        self.assertEqual(u'member', presence.affiliation)
        self.assertEqual(u'participant', presence.role)
        self.assertEqual(JID('hag66@shakespeare.lit/pda'), presence.entity)
        self.assertEqual(u'thirdwitch', presence.nick)



class MUCClientProtocolTest(unittest.TestCase):
    """
    Tests for L{muc.MUCClientProtocol}.
    """

    def setUp(self):
        self.clock = task.Clock()
        self.sessionManager = TestableStreamManager(reactor=self.clock)
        self.stub = self.sessionManager.stub
        self.protocol = muc.MUCClientProtocol(reactor=self.clock)
        self.protocol.setHandlerParent(self.sessionManager)

        self.roomIdentifier = 'test'
        self.service  = 'conference.example.org'
        self.nick = 'Nick'

        self.occupantJID = JID(tuple=(self.roomIdentifier,
                                      self.service,
                                      self.nick))
        self.roomJID = self.occupantJID.userhostJID()
        self.userJID = JID('test@example.org/Testing')


    def test_initNoReactor(self):
        """
        If no reactor is passed, the default reactor is used.
        """
        protocol = muc.MUCClientProtocol()
        from twisted.internet import reactor
        self.assertEqual(reactor, protocol._reactor)


    def test_groupChatReceived(self):
        """
        Messages of type groupchat are parsed and passed to L{groupChatReceived}.
        """
        xml = u"""
            <message to='test@test.com' from='%s' type='groupchat'>
              <body>test</body>
            </message>
        """ % (self.occupantJID)

        def groupChatReceived(message):
            self.assertEquals('test', message.body, "Wrong group chat message")
            self.assertEquals(self.roomIdentifier, message.sender.user,
                              'Wrong room identifier')

        d, self.protocol.groupChatReceived = calledAsync(groupChatReceived)
        self.stub.send(parseXml(xml))
        return d


    def test_groupChatReceivedNotOverridden(self):
        """
        If L{groupChatReceived} has not been overridden, no errors should occur.
        """
        xml = u"""
            <message to='test@test.com' from='%s' type='groupchat'>
              <body>test</body>
            </message>
        """ % (self.occupantJID)

        self.stub.send(parseXml(xml))


    def test_join(self):
        """
        Joining a room waits for confirmation, deferred fires user presence.
        """

        def cb(presence):
            self.assertEquals(self.occupantJID, presence.sender)

        # Join the room
        d = self.protocol.join(self.roomJID, self.nick)
        d.addCallback(cb)

        element = self.stub.output[-1]

        self.assertEquals('presence', element.name, "Need to be presence")
        self.assertNotIdentical(None, element.x, 'No muc x element')

        # send back user presence, they joined
        xml = """
            <presence from='%s@%s/%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.roomIdentifier, self.service, self.nick)
        self.stub.send(parseXml(xml))
        return d


    def test_joinHistory(self):
        """
        Passing a history parameter sends a 'maxStanzas' history limit.
        """

        historyOptions = muc.HistoryOptions(maxStanzas=10)
        d = self.protocol.join(self.roomJID, self.nick,
                               historyOptions)

        element = self.stub.output[-1]
        query = "/*/x[@xmlns='%s']/history[@xmlns='%s']" % (muc.NS_MUC,
                                                            muc.NS_MUC)
        result = xpath.queryForNodes(query, element)
        history = result[0]
        self.assertEquals('10', history.getAttribute('maxstanzas'))

        # send back user presence, they joined
        xml = """
            <presence from='%s@%s/%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.roomIdentifier, self.service, self.nick)
        self.stub.send(parseXml(xml))
        return d


    def test_joinForbidden(self):
        """
        A forbidden error in response to a join errbacks with L{StanzaError}.
        """

        def cb(error):
            self.assertEquals('forbidden', error.condition,
                              'Wrong muc condition')

        d = self.protocol.join(self.roomJID, self.nick)
        self.assertFailure(d, StanzaError)
        d.addCallback(cb)

        # send back error, forbidden
        xml = u"""
            <presence from='%s' type='error'>
              <error type='auth'>
                <forbidden xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
              </error>
            </presence>
        """ % (self.occupantJID)
        self.stub.send(parseXml(xml))
        return d


    def test_joinForbiddenFromRoomJID(self):
        """
        An error response to a join sent from the room JID should errback.

        Some service implementations send error stanzas from the room JID
        instead of the JID the join presence was sent to.
        """

        d = self.protocol.join(self.roomJID, self.nick)
        self.assertFailure(d, StanzaError)

        # send back error, forbidden
        xml = u"""
            <presence from='%s' type='error'>
              <error type='auth'>
                <forbidden xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
              </error>
            </presence>
        """ % (self.roomJID)
        self.stub.send(parseXml(xml))
        return d


    def test_joinBadJID(self):
        """
        Client joining a room and getting a jid-malformed error.
        """

        def cb(error):
            self.assertEquals('jid-malformed', error.condition,
                              'Wrong muc condition')

        d = self.protocol.join(self.roomJID, self.nick)
        self.assertFailure(d, StanzaError)
        d.addCallback(cb)

        # send back error, bad JID
        xml = u"""
            <presence from='%s' type='error'>
              <error type='modify'>
                <jid-malformed xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
              </error>
            </presence>
        """ % (self.occupantJID)
        self.stub.send(parseXml(xml))
        return d


    def test_joinTimeout(self):
        """
        After not receiving a response to a join, errback with L{TimeoutError}.
        """

        d = self.protocol.join(self.roomJID, self.nick)
        self.assertFailure(d, TimeoutError)
        self.clock.advance(muc.DEFER_TIMEOUT)
        return d


    def test_joinPassword(self):
        """
        Sending a password via presence to a password protected room.
        """

        self.protocol.join(self.roomJID, self.nick, password='secret')

        element = self.stub.output[-1]

        self.assertTrue(xpath.matches(
                u"/presence[@to='%s']/x/password"
                    "[text()='secret']" % (self.occupantJID,),
                element),
            'Wrong presence stanza')


    def test_nick(self):
        """
        Send a nick change to the server.
        """
        newNick = 'newNick'

        def cb(presence):
            self.assertEquals(JID(tuple=(self.roomIdentifier,
                                         self.service,
                                         newNick)),
                              presence.sender)

        d = self.protocol.nick(self.roomJID, newNick)
        d.addCallback(cb)

        element = self.stub.output[-1]
        self.assertEquals('presence', element.name, "Need to be presence")
        self.assertNotIdentical(None, element.x, 'No muc x element')

        # send back user presence, nick changed
        xml = u"""
            <presence from='%s/%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.roomJID, newNick)
        self.stub.send(parseXml(xml))
        return d


    def test_nickConflict(self):
        """
        If the server finds the new nick in conflict, the errback is called.
        """
        newNick = 'newNick'

        d = self.protocol.nick(self.roomJID, newNick)
        self.assertFailure(d, StanzaError)

        element = self.stub.output[-1]
        self.assertEquals('presence', element.name, "Need to be presence")
        self.assertNotIdentical(None, element.x, 'No muc x element')

        # send back error presence, nick conflicted
        xml = u"""
            <presence from='%s/%s' type='error'>
                <x xmlns='http://jabber.org/protocol/muc'/>
                <error type='cancel'>
                  <conflict xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
                </error>
            </presence>
        """ % (self.roomJID, newNick)
        self.stub.send(parseXml(xml))
        return d


    def test_status(self):
        """
        Change status
        """
        def joined(_):
            d = self.protocol.status(self.roomJID, 'xa', 'testing MUC')
            d.addCallback(statusChanged)
            return d

        def statusChanged(presence):
            self.assertEqual(self.occupantJID, presence.sender)

        # Join the room
        d = self.protocol.join(self.roomJID, self.nick)
        d.addCallback(joined)

        # Receive presence back from the room: joined.
        xml = u"""
            <presence to='%s' from='%s'/>
        """ % (self.userJID, self.occupantJID)
        self.stub.send(parseXml(xml))

        # The presence for the status change should have been sent now.
        element = self.stub.output[-1]

        self.assertEquals('presence', element.name, "Need to be presence")
        self.assertTrue(getattr(element, 'x', None), 'No muc x element')

        # send back user presence, status changed
        xml = u"""
            <presence from='%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
              <show>xa</show>
              <status>testing MUC</status>
            </presence>
        """ % self.occupantJID
        self.stub.send(parseXml(xml))

        return d


    def test_leave(self):
        """
        Client leaves a room
        """
        def joined(_):
            return self.protocol.leave(self.roomJID)

        # Join the room
        d = self.protocol.join(self.roomJID, self.nick)
        d.addCallback(joined)

        # Receive presence back from the room: joined.
        xml = u"""
            <presence to='%s' from='%s'/>
        """ % (self.userJID, self.occupantJID)
        self.stub.send(parseXml(xml))

        # The presence for leaving the room should have been sent now.
        element = self.stub.output[-1]

        self.assertEquals('unavailable', element['type'],
                          'Unavailable is not being sent')

        # Receive presence back from the room: left.
        xml = u"""
            <presence to='%s' from='%s' type='unavailable'/>
        """ % (self.userJID, self.occupantJID)
        self.stub.send(parseXml(xml))

        return d


    def test_groupChat(self):
        """
        Send private messages to muc entities.
        """
        self.protocol.groupChat(self.roomJID, u'This is a test')

        message = self.stub.output[-1]

        self.assertEquals('message', message.name)
        self.assertEquals(self.roomJID.full(), message.getAttribute('to'))
        self.assertEquals('groupchat', message.getAttribute('type'))
        self.assertEquals(u'This is a test', unicode(message.body))


    def test_chat(self):
        """
        Send private messages to muc entities.
        """
        otherOccupantJID = JID(self.occupantJID.userhost()+'/OtherNick')

        self.protocol.chat(otherOccupantJID, u'This is a test')

        message = self.stub.output[-1]

        self.assertEquals('message', message.name)
        self.assertEquals(otherOccupantJID.full(), message.getAttribute('to'))
        self.assertEquals('chat', message.getAttribute('type'))
        self.assertEquals(u'This is a test', unicode(message.body))


    def test_subject(self):
        """
        Change subject of the room.
        """
        self.protocol.subject(self.roomJID, u'This is a test')

        message = self.stub.output[-1]

        self.assertEquals('message', message.name)
        self.assertEquals(self.roomJID.full(), message.getAttribute('to'))
        self.assertEquals('groupchat', message.getAttribute('type'))
        self.assertEquals(u'This is a test', unicode(message.subject))


    def test_invite(self):
        """
        Invite a user to a room
        """
        invitee = JID('other@example.org')

        self.protocol.invite(self.roomJID, invitee, u'This is a test')

        message = self.stub.output[-1]

        self.assertEquals('message', message.name)
        self.assertEquals(self.roomJID.full(), message.getAttribute('to'))
        self.assertEquals(muc.NS_MUC_USER, message.x.uri)
        self.assertEquals(muc.NS_MUC_USER, message.x.invite.uri)
        self.assertEquals(invitee.full(), message.x.invite.getAttribute('to'))
        self.assertEquals(muc.NS_MUC_USER, message.x.invite.reason.uri)
        self.assertEquals(u'This is a test', unicode(message.x.invite.reason))


    def test_getRegisterForm(self):
        """
        The response of a register form request should extract the form.
        """

        def cb(form):
            self.assertEquals('form', form.formType)

        d = self.protocol.getRegisterForm(self.roomJID)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        query = "/iq/query[@xmlns='%s']" % (muc.NS_REGISTER)
        nodes = xpath.queryForNodes(query, iq)
        self.assertNotIdentical(None, nodes, 'Missing query element')

        self.assertRaises(StopIteration, next, nodes[0].elements())

        xml = u"""
            <iq from='%s' id='%s' to='%s' type='result'>
              <query xmlns='jabber:iq:register'>
                <x xmlns='jabber:x:data' type='form'>
                  <field type='hidden'
                         var='FORM_TYPE'>
                    <value>http://jabber.org/protocol/muc#register</value>
                  </field>
                  <field label='Desired Nickname'
                         type='text-single'
                         var='muc#register_roomnick'>
                    <required/>
                  </field>
                </x>
              </query>
            </iq>
        """ % (self.roomJID, iq['id'], self.userJID)
        self.stub.send(parseXml(xml))

        return d


    def test_register(self):
        """
        Client registering with a room.

        http://xmpp.org/extensions/xep-0045.html#register
        """

        def cb(iq):
            # check for a result
            self.assertEquals('result', iq['type'], 'We did not get a result')

        d = self.protocol.register(self.roomJID,
                                   {'muc#register_roomnick': 'thirdwitch'})
        d.addCallback(cb)

        iq = self.stub.output[-1]

        query = "/iq/query[@xmlns='%s']" % muc.NS_REGISTER
        nodes = xpath.queryForNodes(query, iq)
        self.assertNotIdentical(None, nodes, 'Invalid registration request')

        form = data_form.findForm(nodes[0], muc.NS_MUC_REGISTER)
        self.assertNotIdentical(None, form, 'Missing registration form')
        self.assertEquals('submit', form.formType)
        self.assertIn('muc#register_roomnick', form.fields)


        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_registerCancel(self):
        """
        Cancelling a registration request sends a cancel form.
        """

        d = self.protocol.register(self.roomJID, None)

        iq = self.stub.output[-1]

        query = "/iq/query[@xmlns='%s']" % muc.NS_REGISTER
        nodes = xpath.queryForNodes(query, iq)
        self.assertNotIdentical(None, nodes, 'Invalid registration request')

        form = data_form.findForm(nodes[0], muc.NS_MUC_REGISTER)
        self.assertNotIdentical(None, form, 'Missing registration form')
        self.assertEquals('cancel', form.formType)

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_voice(self):
        """
        Client requesting voice for a room.
        """
        self.protocol.voice(self.occupantJID)

        m = self.stub.output[-1]

        query = ("/message/x[@type='submit']/field/value"
                    "[text()='%s']") % muc.NS_MUC_REQUEST
        self.assertTrue(xpath.matches(query, m), 'Invalid voice message stanza')


    def test_history(self):
        """
        Converting a one to one chat to a multi-user chat.
        """
        archive = []
        thread = "e0ffe42b28561960c6b12b944a092794b9683a38"
        # create messages
        element = domish.Element((None, 'message'))
        element['to'] = 'testing@example.com'
        element['type'] = 'chat'
        element.addElement('body', None, 'test')
        element.addElement('thread', None, thread)

        archive.append({'stanza': element,
                        'timestamp': datetime(2002, 10, 13, 23, 58, 37,
                                              tzinfo=tzutc())})

        element = domish.Element((None, 'message'))
        element['to'] = 'testing2@example.com'
        element['type'] = 'chat'
        element.addElement('body', None, 'yo')
        element.addElement('thread', None, thread)

        archive.append({'stanza': element,
                        'timestamp': datetime(2002, 10, 13, 23, 58, 43,
                                              tzinfo=tzutc())})

        self.protocol.history(self.occupantJID, archive)


        while len(self.stub.output)>0:
            element = self.stub.output.pop()
            # check for delay element
            self.assertEquals('message', element.name, 'Wrong stanza')
            self.assertTrue(xpath.matches("/message/delay", element),
                            'Invalid history stanza')


    def test_getConfiguration(self):
        """
        The response of a configure form request should extract the form.
        """

        def cb(form):
            self.assertEquals('form', form.formType)

        d = self.protocol.getConfiguration(self.roomJID)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        query = "/iq/query[@xmlns='%s']" % (muc.NS_MUC_OWNER)
        nodes = xpath.queryForNodes(query, iq)
        self.assertNotIdentical(None, nodes, 'Missing query element')

        self.assertRaises(StopIteration, next, nodes[0].elements())

        xml = u"""
            <iq from='%s' id='%s' to='%s' type='result'>
              <query xmlns='http://jabber.org/protocol/muc#owner'>
                <x xmlns='jabber:x:data' type='form'>
                  <field type='hidden'
                         var='FORM_TYPE'>
                    <value>http://jabber.org/protocol/muc#roomconfig</value>
                  </field>
                  <field label='Natural-Language Room Name'
                         type='text-single'
                         var='muc#roomconfig_roomname'/>
                </x>
              </query>
            </iq>
        """ % (self.roomJID, iq['id'], self.userJID)
        self.stub.send(parseXml(xml))

        return d


    def test_getConfigurationNoOptions(self):
        """
        The response of a configure form request should extract the form.
        """

        def cb(form):
            self.assertIdentical(None, form)

        d = self.protocol.getConfiguration(self.roomJID)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        xml = u"""
            <iq from='%s' id='%s' to='%s' type='result'>
              <query xmlns='http://jabber.org/protocol/muc#owner'/>
            </iq>
        """ % (self.roomJID, iq['id'], self.userJID)
        self.stub.send(parseXml(xml))

        return d


    def test_configure(self):
        """
        Default configure and changing the room name.
        """

        def cb(iq):
            self.assertEquals('result', iq['type'], 'Not a result')

        values = {'muc#roomconfig_roomname': self.roomIdentifier}

        d = self.protocol.configure(self.roomJID, values)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        self.assertEquals('set', iq.getAttribute('type'))
        self.assertEquals(self.roomJID.full(), iq.getAttribute('to'))

        query = "/iq/query[@xmlns='%s']" % (muc.NS_MUC_OWNER)
        nodes = xpath.queryForNodes(query, iq)
        self.assertNotIdentical(None, nodes, 'Bad configure request')

        form = data_form.findForm(nodes[0], muc.NS_MUC_CONFIG)
        self.assertNotIdentical(None, form, 'Missing configuration form')
        self.assertEquals('submit', form.formType)

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_configureEmpty(self):
        """
        Accept default configuration by sending an empty form.
        """

        values = {}

        d = self.protocol.configure(self.roomJID, values)

        iq = self.stub.output[-1]

        query = "/iq/query[@xmlns='%s']" % (muc.NS_MUC_OWNER)
        nodes = xpath.queryForNodes(query, iq)

        form = data_form.findForm(nodes[0], muc.NS_MUC_CONFIG)
        self.assertNotIdentical(None, form, 'Missing configuration form')
        self.assertEquals('submit', form.formType)

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_configureCancel(self):
        """
        Cancelling room configuration should send a cancel form.
        """

        d = self.protocol.configure(self.roomJID, None)

        iq = self.stub.output[-1]

        query = "/iq/query[@xmlns='%s']" % (muc.NS_MUC_OWNER)
        nodes = xpath.queryForNodes(query, iq)

        form = data_form.findForm(nodes[0], muc.NS_MUC_CONFIG)
        self.assertNotIdentical(None, form, 'Missing configuration form')
        self.assertEquals('cancel', form.formType)

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_getMemberList(self):
        """
        Retrieving the member list returns a list of L{muc.AdminItem}s

        The request asks for the affiliation C{'member'}.
        """
        def cb(items):
            self.assertEquals(1, len(items))
            item = items[0]
            self.assertEquals(JID(u'hag66@shakespeare.lit'), item.entity)
            self.assertEquals(u'thirdwitch', item.nick)
            self.assertEquals(u'member', item.affiliation)

        d = self.protocol.getMemberList(self.roomJID)
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('get', iq.getAttribute('type'))
        query = "/iq/query[@xmlns='%s']/item[@xmlns='%s']" % (muc.NS_MUC_ADMIN,
                                                              muc.NS_MUC_ADMIN)
        items = xpath.queryForNodes(query, iq)
        self.assertNotIdentical(None, items)
        self.assertEquals(1, len(items))
        self.assertEquals('member', items[0].getAttribute('affiliation'))

        response = toResponse(iq, 'result')
        query = response.addElement((NS_MUC_ADMIN, 'query'))
        item = query.addElement('item')
        item['affiliation'] ='member'
        item['jid'] = 'hag66@shakespeare.lit'
        item['nick'] = 'thirdwitch'
        item['role'] = 'participant'
        self.stub.send(response)

        return d


    def test_getAdminList(self):
        """
        Retrieving the admin list returns a list of L{muc.AdminItem}s

        The request asks for the affiliation C{'admin'}.
        """
        d = self.protocol.getAdminList(self.roomJID)

        iq = self.stub.output[-1]
        query = "/iq/query[@xmlns='%s']/item[@xmlns='%s']" % (muc.NS_MUC_ADMIN,
                                                              muc.NS_MUC_ADMIN)
        items = xpath.queryForNodes(query, iq)
        self.assertEquals('admin', items[0].getAttribute('affiliation'))

        response = toResponse(iq, 'result')
        query = response.addElement((NS_MUC_ADMIN, 'query'))
        self.stub.send(response)

        return d


    def test_getBanList(self):
        """
        Retrieving the ban list returns a list of L{muc.AdminItem}s

        The request asks for the affiliation C{'outcast'}.
        """
        def cb(items):
            self.assertEquals(1, len(items))
            item = items[0]
            self.assertEquals(JID(u'hag66@shakespeare.lit'), item.entity)
            self.assertEquals(u'outcast', item.affiliation)
            self.assertEquals(u'Trouble making', item.reason)

        d = self.protocol.getBanList(self.roomJID)
        d.addCallback(cb)

        iq = self.stub.output[-1]
        query = "/iq/query[@xmlns='%s']/item[@xmlns='%s']" % (muc.NS_MUC_ADMIN,
                                                              muc.NS_MUC_ADMIN)
        items = xpath.queryForNodes(query, iq)
        self.assertEquals('outcast', items[0].getAttribute('affiliation'))

        response = toResponse(iq, 'result')
        query = response.addElement((NS_MUC_ADMIN, 'query'))
        item = query.addElement('item')
        item['affiliation'] ='outcast'
        item['jid'] = 'hag66@shakespeare.lit'
        item.addElement('reason', content='Trouble making')
        self.stub.send(response)

        return d


    def test_getOwnerList(self):
        """
        Retrieving the owner list returns a list of L{muc.AdminItem}s

        The request asks for the affiliation C{'owner'}.
        """
        d = self.protocol.getOwnerList(self.roomJID)

        iq = self.stub.output[-1]
        query = "/iq/query[@xmlns='%s']/item[@xmlns='%s']" % (muc.NS_MUC_ADMIN,
                                                              muc.NS_MUC_ADMIN)
        items = xpath.queryForNodes(query, iq)
        self.assertEquals('owner', items[0].getAttribute('affiliation'))

        response = toResponse(iq, 'result')
        query = response.addElement((NS_MUC_ADMIN, 'query'))
        self.stub.send(response)

        return d


    def test_getModeratorList(self):
        """
        Retrieving the moderator returns a list of L{muc.AdminItem}s.

        The request asks for the role C{'moderator'}.
        """

        def cb(items):
            self.assertEquals(1, len(items))
            item = items[0]
            self.assertEquals(JID(u'hag66@shakespeare.lit'), item.entity)
            self.assertEquals(u'thirdwitch', item.nick)
            self.assertEquals(u'moderator', item.role)

        d = self.protocol.getModeratorList(self.roomJID)
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('get', iq.getAttribute('type'))
        query = "/iq/query[@xmlns='%s']/item[@xmlns='%s']" % (muc.NS_MUC_ADMIN,
                                                              muc.NS_MUC_ADMIN)
        items = xpath.queryForNodes(query, iq)
        self.assertNotIdentical(None, items)
        self.assertEquals(1, len(items))
        self.assertEquals('moderator', items[0].getAttribute('role'))

        response = toResponse(iq, 'result')
        query = response.addElement((NS_MUC_ADMIN, 'query'))
        item = query.addElement('item')
        item['affiliation'] ='member'
        item['jid'] = 'hag66@shakespeare.lit'
        item['nick'] = 'thirdwitch'
        item['role'] = 'moderator'
        self.stub.send(response)

        return d


    def test_modifyAffiliationList(self):

        entities = [JID('user1@test.example.org'),
                    JID('user2@test.example.org')]
        d = self.protocol.modifyAffiliationList(self.roomJID, entities,
                                                'admin')

        iq = self.stub.output[-1]
        query = "/iq/query[@xmlns='%s']/item[@xmlns='%s']" % (muc.NS_MUC_ADMIN,
                                                              muc.NS_MUC_ADMIN)
        items = xpath.queryForNodes(query, iq)
        self.assertNotIdentical(None, items)
        self.assertEquals(entities[0], JID(items[0].getAttribute('jid')))
        self.assertEquals('admin', items[0].getAttribute('affiliation'))
        self.assertEquals(entities[1], JID(items[1].getAttribute('jid')))
        self.assertEquals('admin', items[1].getAttribute('affiliation'))

        # Send a response to have the deferred fire.
        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_grantVoice(self):
        """
        Granting voice sends request to set role to 'participant'.
        """
        nick = 'TroubleMaker'
        def cb(give_voice):
            self.assertTrue(give_voice, 'Did not give voice user')

        d = self.protocol.grantVoice(self.roomJID, nick,
                                     sender=self.userJID)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        query = (u"/iq[@type='set' and @to='%s']/query/item"
                     "[@role='participant']") % self.roomJID
        self.assertTrue(xpath.matches(query, iq), 'Wrong voice stanza')

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_revokeVoice(self):
        """
        Revoking voice sends request to set role to 'visitor'.
        """
        nick = 'TroubleMaker'

        d = self.protocol.revokeVoice(self.roomJID, nick,
                                      reason="Trouble maker",
                                      sender=self.userJID)

        iq = self.stub.output[-1]

        query = (u"/iq[@type='set' and @to='%s']/query/item"
                     "[@role='visitor']") % self.roomJID
        self.assertTrue(xpath.matches(query, iq), 'Wrong voice stanza')

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_grantModerator(self):
        """
        Granting moderator privileges sends request to set role to 'moderator'.
        """
        nick = 'TroubleMaker'

        d = self.protocol.grantModerator(self.roomJID, nick,
                                         sender=self.userJID)

        iq = self.stub.output[-1]

        query = (u"/iq[@type='set' and @to='%s']/query/item"
                     "[@role='moderator']") % self.roomJID
        self.assertTrue(xpath.matches(query, iq), 'Wrong voice stanza')

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d


    def test_ban(self):
        """
        Ban an entity in a room.
        """
        banned = JID('ban@jabber.org/TroubleMaker')

        def cb(banned):
            self.assertTrue(banned, 'Did not ban user')

        d = self.protocol.ban(self.roomJID, banned, reason='Spam',
                              sender=self.userJID)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        self.assertTrue(xpath.matches(
                u"/iq[@type='set' and @to='%s']/query/item"
                    "[@affiliation='outcast']" % (self.roomJID,),
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

        d = self.protocol.kick(self.roomJID, nick, reason='Spam',
                               sender=self.userJID)
        d.addCallback(cb)

        iq = self.stub.output[-1]

        self.assertTrue(xpath.matches(
                u"/iq[@type='set' and @to='%s']/query/item"
                    "[@role='none']" % (self.roomJID,),
                iq),
            'Wrong kick stanza')

        response = toResponse(iq, 'result')
        self.stub.send(response)

        return d


    def test_destroy(self):
        """
        Destroy a room.
        """
        d = self.protocol.destroy(self.occupantJID, reason='Time to leave',
                                  alternate=JID('other@%s' % self.service),
                                  password='secret')

        iq = self.stub.output[-1]

        query = ("/iq[@type='set']/query[@xmlns='%s']/destroy[@xmlns='%s']" %
                 (muc.NS_MUC_OWNER, muc.NS_MUC_OWNER))

        nodes = xpath.queryForNodes(query, iq)
        self.assertNotIdentical(None, nodes, 'Bad configure request')
        destroy = nodes[0]
        self.assertEquals('Time to leave', unicode(destroy.reason))

        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d



class MUCClientTest(unittest.TestCase):
    """
    Tests for C{muc.MUCClient}.
    """

    def setUp(self):
        self.clock = task.Clock()
        self.sessionManager = TestableStreamManager(reactor=self.clock)
        self.stub = self.sessionManager.stub
        self.protocol = muc.MUCClient(reactor=self.clock)
        self.protocol.setHandlerParent(self.sessionManager)

        self.roomIdentifier = 'test'
        self.service  = 'conference.example.org'
        self.nick = 'Nick'

        self.occupantJID = JID(tuple=(self.roomIdentifier,
                                      self.service,
                                      self.nick))
        self.roomJID = self.occupantJID.userhostJID()
        self.userJID = JID('test@example.org/Testing')


    def _createRoom(self):
        """
        A helper method to create a test room.
        """
        # create a room
        room = muc.Room(self.roomJID, self.nick)
        self.protocol._addRoom(room)
        return room


    def test_interface(self):
        """
        Do instances of L{muc.MUCClient} provide L{iwokkel.IMUCClient}?
        """
        verify.verifyObject(iwokkel.IMUCClient, self.protocol)


    def _testPresence(self, sender='', available=True):
        """
        Helper for presence tests.
        """
        def userUpdatedStatus(room, user, show, status):
            self.fail("Unexpected call to userUpdatedStatus")

        def userJoinedRoom(room, user):
            self.fail("Unexpected call to userJoinedRoom")

        if available:
            available = ""
        else:
            available = " type='unavailable'"

        if sender:
            sender = u" from='%s'" % sender

        xml = u"""
            <presence to='%s'%s%s>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.userJID, sender, available)

        self.protocol.userUpdatedStatus = userUpdatedStatus
        self.protocol.userJoinedRoom = userJoinedRoom
        self.stub.send(parseXml(xml))


    def test_availableReceivedEmptySender(self):
        """
        Availability presence from empty sender is ignored.
        """
        self._testPresence(sender='')


    def test_availableReceivedNotInRoom(self):
        """
        Availability presence from unknown entities is ignored.
        """
        otherOccupantJID = JID(self.occupantJID.userhost()+'/OtherNick')
        self._testPresence(sender=otherOccupantJID)


    def test_availableReceivedSetsUserRole(self):
        """
        The role received in a presence update is stored on the user.
        """
        room = self._createRoom()
        user = muc.User(self.nick)
        room.addUser(user)
        self.assertEquals('none', user.role)

        xml = u"""
            <presence to='%s' from='%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.userJID, self.occupantJID)
        self.stub.send(parseXml(xml))

        self.assertEquals('participant', user.role)


    def test_availableReceivedSetsUserAffiliation(self):
        """
        The affiliation received in a presence update is stored on the user.
        """
        room = self._createRoom()
        user = muc.User(self.nick)
        room.addUser(user)
        self.assertEquals('none', user.affiliation)

        xml = u"""
            <presence to='%s' from='%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.userJID, self.occupantJID)
        self.stub.send(parseXml(xml))
        self.assertEquals('member', user.affiliation)


    def test_unavailableReceivedEmptySender(self):
        """
        Availability presence from empty sender is ignored.
        """
        self._testPresence(sender='', available=False)


    def test_unavailableReceivedNotInRoom(self):
        """
        Availability presence from unknown entities is ignored.
        """
        otherOccupantJID = JID(self.occupantJID.userhost()+'/OtherNick')
        self._testPresence(sender=otherOccupantJID, available=False)


    def test_unavailableReceivedNotInRoster(self):
        """
        Availability presence from unknown entities is ignored.
        """
        room = self._createRoom()
        user = muc.User(self.nick)
        room.addUser(user)
        otherOccupantJID = JID(self.occupantJID.userhost()+'/OtherNick')
        self._testPresence(sender=otherOccupantJID, available=False)


    def test_userJoinedRoom(self):
        """
        Joins by others to a room we're in are passed to userJoinedRoom
        """
        xml = """
            <presence to='%s' from='%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.userJID.full(), self.occupantJID.full())

        # create a room
        self._createRoom()

        def userJoinedRoom(room, user):
            self.assertEquals(self.roomJID, room.roomJID,
                              'Wrong room name')
            self.assertTrue(room.inRoster(user), 'User not in roster')

        d, self.protocol.userJoinedRoom = calledAsync(userJoinedRoom)
        self.stub.send(parseXml(xml))
        return d


    def test_receivedSubject(self):
        """
        Subject received from a room we're in are passed to receivedSubject.
        """
        xml = u"""
            <message to='%s' from='%s' type='groupchat'>
              <subject>test</subject>
            </message>
        """ % (self.userJID, self.occupantJID)

        self._createRoom()

        # add user to room
        user = muc.User(self.nick)
        room = self.protocol._getRoom(self.roomJID)
        room.addUser(user)

        def receivedSubject(room, user, subject):
            self.assertEquals('test', subject, "Wrong group chat message")
            self.assertEquals(self.roomJID, room.roomJID,
                              'Wrong room name')
            self.assertEquals(self.nick, user.nick)

        d, self.protocol.receivedSubject = calledAsync(receivedSubject)
        self.stub.send(parseXml(xml))
        return d


    def test_receivedSubjectNotOverridden(self):
        """
        Not overriding receivedSubject is ok.
        """
        xml = u"""
            <message to='%s' from='%s' type='groupchat'>
              <subject>test</subject>
            </message>
        """ % (self.userJID, self.occupantJID)

        self._createRoom()
        self.stub.send(parseXml(xml))


    def test_receivedGroupChat(self):
        """
        Messages received from a room we're in are passed to receivedGroupChat.
        """
        xml = u"""
            <message to='test@test.com' from='%s' type='groupchat'>
              <body>test</body>
            </message>
        """ % (self.occupantJID)

        self._createRoom()

        def receivedGroupChat(room, user, message):
            self.assertEquals('test', message.body, "Wrong group chat message")
            self.assertEquals(self.roomJID, room.roomJID,
                              'Wrong room name')

        d, self.protocol.receivedGroupChat = calledAsync(receivedGroupChat)
        self.stub.send(parseXml(xml))
        return d


    def test_receivedGroupChatRoom(self):
        """
        Messages received from the room itself have C{user} set to C{None}.
        """
        xml = u"""
            <message to='test@test.com' from='%s' type='groupchat'>
              <body>test</body>
            </message>
        """ % (self.roomJID)

        self._createRoom()

        def receivedGroupChat(room, user, message):
            self.assertIdentical(None, user)

        d, self.protocol.receivedGroupChat = calledAsync(receivedGroupChat)
        self.stub.send(parseXml(xml))
        return d


    def test_receivedGroupChatNotInRoom(self):
        """
        Messages received from a room we're not in are ignored.
        """
        xml = u"""
            <message to='test@test.com' from='%s' type='groupchat'>
              <body>test</body>
            </message>
        """ % (self.occupantJID)

        def receivedGroupChat(room, user, message):
            self.fail("Unexpected call to receivedGroupChat")

        self.protocol.receivedGroupChat = receivedGroupChat
        self.stub.send(parseXml(xml))


    def test_receivedGroupChatNotOverridden(self):
        """
        Not overriding receivedGroupChat is ok.
        """
        xml = u"""
            <message to='test@test.com' from='%s' type='groupchat'>
              <body>test</body>
            </message>
        """ % (self.occupantJID)

        self._createRoom()
        self.stub.send(parseXml(xml))


    def test_join(self):
        """
        Joining a room waits for confirmation, deferred fires room.
        """

        def cb(room):
            self.assertEqual(self.roomJID, room.roomJID)
            self.assertFalse(room.locked)

        d = self.protocol.join(self.roomJID, self.nick)
        d.addCallback(cb)

        # send back user presence, they joined
        xml = """
            <presence from='%s@%s/%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.roomIdentifier, self.service, self.nick)
        self.stub.send(parseXml(xml))
        return d


    def test_joinLocked(self):
        """
        A new room is locked by default.
        """

        def cb(room):
            self.assertTrue(room.locked, "Room is not marked as locked")

        d = self.protocol.join(self.roomJID, self.nick)
        d.addCallback(cb)

        # send back user presence, they joined
        xml = """
            <presence from='%s@%s/%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='owner' role='moderator'/>
                <status code="110"/>
                <status code="201"/>
              </x>
            </presence>
        """ % (self.roomIdentifier, self.service, self.nick)
        self.stub.send(parseXml(xml))
        return d


    def test_joinForbidden(self):
        """
        A forbidden error in response to a join errbacks with L{StanzaError}.
        """

        def cb(error):
            self.assertEquals('forbidden', error.condition,
                              'Wrong muc condition')
            self.assertIdentical(None, self.protocol._getRoom(self.roomJID))


        d = self.protocol.join(self.roomJID, self.nick)
        self.assertFailure(d, StanzaError)
        d.addCallback(cb)

        # send back error, forbidden
        xml = u"""
            <presence from='%s' type='error'>
              <error type='auth'>
                <forbidden xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
              </error>
            </presence>
        """ % (self.occupantJID)
        self.stub.send(parseXml(xml))
        return d


    def test_userLeftRoom(self):
        """
        Unavailable presence from a participant removes it from the room.
        """

        xml = u"""
            <presence to='%s' from='%s' type='unavailable'/>
        """ % (self.userJID, self.occupantJID)

        # create a room
        self._createRoom()

        # add user to room
        user = muc.User(self.nick)
        room = self.protocol._getRoom(self.roomJID)
        room.addUser(user)

        def userLeftRoom(room, user):
            self.assertEquals(self.roomJID, room.roomJID,
                              'Wrong room name')
            self.assertFalse(room.inRoster(user), 'User in roster')

        d, self.protocol.userLeftRoom = calledAsync(userLeftRoom)
        self.stub.send(parseXml(xml))
        return d


    def test_receivedHistory(self):
        """
        Receiving history on room join.
        """
        xml = u"""
            <message to='test@test.com' from='%s' type='groupchat'>
              <body>test</body>
              <delay xmlns='urn:xmpp:delay' stamp="2002-10-13T23:58:37Z"
                                            from="%s"/>
            </message>
        """ % (self.occupantJID, self.userJID)

        self._createRoom()


        def receivedHistory(room, user, message):
            self.assertEquals('test', message.body, "wrong message body")
            stamp = datetime(2002, 10, 13, 23, 58, 37, tzinfo=tzutc())
            self.assertEquals(stamp, message.delay.stamp,
                             'Does not have a history stamp')

        d, self.protocol.receivedHistory = calledAsync(receivedHistory)
        self.stub.send(parseXml(xml))
        return d


    def test_receivedHistoryNotOverridden(self):
        """
        Not overriding receivedHistory is ok.
        """
        xml = u"""
            <message to='test@test.com' from='%s' type='groupchat'>
              <body>test</body>
              <delay xmlns='urn:xmpp:delay' stamp="2002-10-13T23:58:37Z"
                                            from="%s"/>
            </message>
        """ % (self.occupantJID, self.userJID)

        self._createRoom()
        self.stub.send(parseXml(xml))


    def test_nickConflict(self):
        """
        If the server finds the new nick in conflict, the errback is called.
        """

        def cb(failure, room):
            user = room.getUser(otherNick)
            self.assertNotIdentical(None, user)
            self.assertEqual(otherJID, user.entity)

        def joined(room):
            d = self.protocol.nick(room.roomJID, otherNick)
            self.assertFailure(d, StanzaError)
            d.addCallback(cb, room)

        otherJID = JID('other@example.org/Home')
        otherNick = 'otherNick'

        d = self.protocol.join(self.roomJID, self.nick)
        d.addCallback(joined)

        # Send back other partipant's presence.
        xml = u"""
            <presence from='%s/%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant' jid='%s'/>
              </x>
            </presence>
        """ % (self.roomJID, otherNick, otherJID)
        self.stub.send(parseXml(xml))

        # send back user presence, they joined
        xml = u"""
            <presence from='%s/%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.roomJID, self.nick)
        self.stub.send(parseXml(xml))

        # send back error presence, nick conflicted
        xml = u"""
            <presence from='%s/%s' type='error'>
                <x xmlns='http://jabber.org/protocol/muc'/>
                <error type='cancel'>
                  <conflict xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
                </error>
            </presence>
        """ % (self.roomJID, otherNick)
        self.stub.send(parseXml(xml))
        return d


    def test_nick(self):
        """
        Send a nick change to the server.
        """
        newNick = 'newNick'

        room = self._createRoom()

        def joined(room):
            self.assertEqual(self.roomJID, room.roomJID)
            self.assertEqual(newNick, room.nick)
            user = room.getUser(newNick)
            self.assertNotIdentical(None, user)
            self.assertEqual(newNick, user.nick)

        d = self.protocol.nick(self.roomJID, newNick)
        d.addCallback(joined)

        # Nick should not have been changed, yet, as we haven't gotten
        # confirmation, yet.

        self.assertEquals(self.nick, room.nick)

        # send back user presence, nick changed
        xml = u"""
            <presence from='%s/%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
            </presence>
        """ % (self.roomJID, newNick)

        self.stub.send(parseXml(xml))
        return d


    def test_leave(self):
        """
        Client leaves a room
        """
        def joined(_):
            return self.protocol.leave(self.roomJID)

        def left(_):
            self.assertIdentical(None, self.protocol._getRoom(self.roomJID))

        # Join the room
        d = self.protocol.join(self.roomJID, self.nick)
        d.addCallback(joined)
        d.addCallback(left)

        # Receive presence back from the room: joined.
        xml = u"""
            <presence to='%s' from='%s'/>
        """ % (self.userJID, self.occupantJID)
        self.stub.send(parseXml(xml))

        # Receive presence back from the room: left.
        xml = u"""
            <presence to='%s' from='%s' type='unavailable'/>
        """ % (self.userJID, self.occupantJID)
        self.stub.send(parseXml(xml))

        return d


    def test_status(self):
        """
        Change status
        """
        def joined(_):
            d = self.protocol.status(self.roomJID, 'xa', 'testing MUC')
            d.addCallback(statusChanged)
            return d

        def statusChanged(room):
            self.assertEqual(self.roomJID, room.roomJID)
            user = room.getUser(self.nick)
            self.assertNotIdentical(None, user, 'User not found')
            self.assertEqual('testing MUC', user.status, 'Wrong status')
            self.assertEqual('xa', user.show, 'Wrong show')

        # Join the room
        d = self.protocol.join(self.roomJID, self.nick)
        d.addCallback(joined)

        # Receive presence back from the room: joined.
        xml = u"""
            <presence to='%s' from='%s'/>
        """ % (self.userJID, self.occupantJID)
        self.stub.send(parseXml(xml))

        # send back user presence, status changed
        xml = u"""
            <presence from='%s'>
              <x xmlns='http://jabber.org/protocol/muc#user'>
                <item affiliation='member' role='participant'/>
              </x>
              <show>xa</show>
              <status>testing MUC</status>
            </presence>
        """ % self.occupantJID

        self.stub.send(parseXml(xml))
        return d


    def test_destroy(self):
        """
        Destroy a room.
        """
        def destroyed(_):
            self.assertIdentical(None, self.protocol._getRoom(self.roomJID))

        d = self.protocol.destroy(self.occupantJID, reason='Time to leave',
                                  alternate=JID('other@%s' % self.service),
                                  password='secret')
        d.addCallback(destroyed)

        iq = self.stub.output[-1]
        response = toResponse(iq, 'result')
        self.stub.send(response)
        return d
