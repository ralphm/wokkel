# -*- test-case-name: wokkel.test.test_muc -*-
#
# Copyright (c) 2003-2009 Ralph Meijer
# See LICENSE for details.

"""
XMPP Multi-User Chat protocol.

This protocol is specified in
U{XEP-0045<http://www.xmpp.org/extensions/xep-0045.html>}.
"""
import datetime

from zope.interface import implements

from twisted.internet import defer, reactor
from twisted.words.protocols.jabber import jid, error, xmlstream
from twisted.words.xish import domish

from wokkel import data_form, xmppim
from wokkel.subprotocols import XMPPHandler
from wokkel.iwokkel import IMUCClient

# Multi User Chat namespaces
NS_MUC = 'http://jabber.org/protocol/muc'
NS_MUC_USER = NS_MUC + '#user'
NS_MUC_ADMIN = NS_MUC + '#admin'
NS_MUC_OWNER = NS_MUC + '#owner'
NS_MUC_ROOMINFO = NS_MUC + '#roominfo'
NS_MUC_CONFIG = NS_MUC + '#roomconfig'
NS_MUC_REQUEST = NS_MUC + '#request'
NS_MUC_REGISTER = NS_MUC + '#register'

NS_DELAY = 'urn:xmpp:delay'
NS_JABBER_DELAY = 'jabber:x:delay'

NS_REQUEST = 'jabber:iq:register'

# Iq get and set XPath queries
IQ = '/iq'
IQ_GET = IQ+'[@type="get"]'
IQ_SET = IQ+'[@type="set"]'

IQ_RESULT = IQ+'[@type="result"]'
IQ_ERROR = IQ+'[@type="error"]'

IQ_QUERY = IQ+'/query'
IQ_GET_QUERY = IQ_GET + '/query'
IQ_SET_QUERY = IQ_SET + '/query'

IQ_COMMAND = IQ+'/command'

MUC_ADMIN = IQ_QUERY+'[@xmlns="' + NS_MUC_ADMIN + '"]'
MUC_OWNER = IQ_QUERY+'[@xmlns="' + NS_MUC_OWNER + '"]'

MUC_AO = MUC_ADMIN + '|' + MUC_OWNER


MESSAGE = '/message'
PRESENCE = '/presence'

CHAT_BODY = MESSAGE +'[@type="chat"]/body'
CHAT = MESSAGE +'[@type="chat"]'

GROUPCHAT = MESSAGE +'[@type="groupchat"]/body'
SUBJECT = MESSAGE +'[@type="groupchat"]/subject'
MESSAGE_ERROR = MESSAGE +'[@type="error"]'

STATUS_CODES = { # see http://www.xmpp.org/extensions/xep-0045.html#registrar-statuscodes
    100:
        {'name':'fulljid',
         'stanza':'presence',

         },
    201:
        {'name':'created',
         'stanza': 'presence',
         'context':'Entering a room',
         'purpose':'Inform user that a new room has been created'
         },
}

STATUS_CODE_CREATED = 201

DEFER_TIMEOUT = 30 # basic timeout is 30 seconds

class JidMalformed(Exception):
    """
    A jid malformed error from the server.

    """
    condition = 'modify'
    mucCondition = 'jid-malformed'



class NotAuthorized(Exception):
    """
    """
    condition = 'auth'
    mucCondition = 'not-authorized'



class RegistrationRequired(Exception):
    """
    """
    condition = 'auth'
    mucCondition = 'registration-required'



class Forbidden(Exception):
    """
    """
    condition = 'auth'
    mucCondition = 'forbidden'



class Conflict(Exception):
    """
    """
    condition = 'cancel'
    mucCondition = 'conflict'



class NotFound(Exception):
    """
    """
    condition = 'cancel'
    mucCondition = 'not-found'



class ServiceUnavailable(Exception):
    """
    """
    condition = 'wait'
    mucCondition = 'service-unavailable'



MUC_EXCEPTIONS = {
    'jid-malformed': JidMalformed,
    'forbidden': Forbidden,
    'not-authorized': NotAuthorized,
    'exception': Exception,
    'conflict': Conflict,
    'service-unavailable': ServiceUnavailable,
    'not-found': NotFound,
    }



class MUCError(error.StanzaError):
    """
    Exception with muc specific condition.
    """
    def __init__(self, condition, mucCondition, type='error', feature=None, text=None):
        appCondition = domish.Element((NS_MUC, mucCondition))
        if feature:
            appCondition['feature'] = feature
        error.StanzaError.__init__(self, condition,
                                         type=type,
                                         text=text,
                                         appCondition=appCondition)



class BadRequest(MUCError):
    """
    Bad request stanza error.
    """
    def __init__(self, mucCondition=None, text=None):
        MUCError.__init__(self, 'bad-request', mucCondition, text)



class Unsupported(MUCError):
    def __init__(self, feature, text=None):
        MUCError.__init__(self, 'feature-not-implemented',
                          'unsupported',
                          feature,
                          text)



class ConfigureRequest(xmlstream.IQ):
    """
    Configure MUC room request.

    http://xmpp.org/extensions/xep-0045.html#roomconfig

    @ivar method: Type attribute of the IQ request. Either C{'set'} or C{'get'}
    @type method: C{str}
    """

    def __init__(self, xs, method='get', fields=[]):
        xmlstream.IQ.__init__(self, xs, method)
        q = self.addElement((NS_MUC_OWNER, 'query'))
        if method == 'set':
            # build data form
            form = data_form.Form('submit', formNamespace=NS_MUC_CONFIG)
            q.addChild(form.toElement())

            for f in fields:
                # create a field
                form.addField(f)



class RegisterRequest(xmlstream.IQ):
    """
    Register room request.

    @ivar method: Type attribute of the IQ request. Either C{'set'} or C{'get'}
    @type method: C{str}
    """

    def __init__(self, xs, method='get', fields=[]):
        xmlstream.IQ.__init__(self, xs, method)
        q = self.addElement((NS_REQUEST, 'query'))
        if method == 'set':
            # build data form
            form_type = 'submit'
            form = data_form.Form(form_type, formNamespace=NS_MUC_REGISTER)
            q.addChild(form.toElement())

            for f in fields:
                # create a field
                form.addField(f)



class AdminRequest(xmlstream.IQ):
    """
    A basic admin iq request.

    @ivar method: Type attribute of the IQ request. Either C{'set'} or C{'get'}
    @type method: C{str}
    """

    def __init__(self, xs, method='get'):
        xmlstream.IQ.__init__(self, xs, method)
        q = self.addElement((NS_MUC_ADMIN, 'query'))



class OwnerRequest(xmlstream.IQ):
    """
    A basic owner iq request.

    @ivar method: Type attribute of the IQ request. Either C{'set'} or C{'get'}
    @type method: C{str}
    """

    def __init__(self, xs, method='get'):
        xmlstream.IQ.__init__(self, xs, method)
        q = self.addElement((NS_MUC_OWNER, 'query'))



class AffiliationRequest(AdminRequest):
    """
    Register room request.

    @ivar method: Type attribute of the IQ request. Either C{'set'} or C{'get'}
    @type method: C{str}

    @ivar affiliation: The affiliation type to send to room.
    @type affiliation: C{str}
    """

    def __init__(self, xs, method='get', affiliation='none',
                       entityOrNick=None, reason=None):
        AdminRequest.__init__(self, xs, method)

        self.affiliation = affiliation
        self.reason = reason
        if entityOrNick:
            self.items([entityOrNick])

    def items(self, entities=None):
        """
        Set or Get the items list for this affiliation request.
        """
        if entities:
            for entityOrNick in entities:
                item = self.query.addElement('item')
                item['affiliation'] = self.affiliation
                try:
                    item['jid'] = entityOrNick.full()
                except AttributeError:
                    item['nick'] = entityOrNick

                if self.reason:
                    item.addElement('reason', content=self.reason)

        return self.query.elements()



class RoleRequest(AdminRequest):
    def __init__(self, xs, method='get', role='none',
                       entityOrNick=None, reason=None):
        AdminRequest.__init__(self, xs, method)

        item = self.query.addElement('item')
        item['role'] = role
        try:
            item['jid'] = entityOrNick.full()
        except AttributeError:
            item['nick'] = entityOrNick

        if reason:
            item.addElement('reason', content=self.reason)



class GroupChat(domish.Element):
    """
        A message stanza of type groupchat. Used to send a message to a MUC room that will be
    broadcasted to people in the room.
    """
    def __init__(self, to, body=None, subject=None, frm=None):
        """
        """
        domish.Element.__init__(self, (None, 'message'))
        self['type'] = 'groupchat'
        if isinstance(to, jid.JID):
            self['to'] = to.userhost()
        else:
            self['to'] = to
        if frm:
            self['from'] = frm
        if body:
            self.addElement('body',None, body)
        if subject:
            self.addElement('subject',None, subject)



class PrivateChat(domish.Element):
    """
        A chat message.
    """
    def __init__(self, to, body=None, frm=None):
        """
        Initialize the L{PrivateChat}

        @param to: The xmpp entity you are sending this chat to.
        @type to: C{unicode} or L{jid.JID}

        @param body: The message you are sending.
        @type body: C{unicode}

        @param frm: The entity that is sending the message.
        @param frm: C{unicode}
        """
        domish.Element.__init__(self, (None, 'message'))
        self['type'] = 'chat'
        if isinstance(to, jid.JID):
            self['to'] = to.userhost()
        else:
            self['to'] = to
        if frm:
            self['from'] = frm
        if body:
            self.addElement('body',None, body)



class InviteMessage(domish.Element):
    def __init__(self, roomJID, invitee, reason=None):
        domish.Element.__init__(self, (None, 'message'))
        self['to'] = unicode(roomJID)
        x = self.addElement('x', NS_MUC_USER)
        invite = x.addElement('invite')
        invite['to'] = invitee
        if reason:
            invite.addElement('reason', None, reason)



class HistoryMessage(GroupChat):
    """
        A history message for MUC groupchat history.
    """
    def __init__(self, to, stamp, body=None, subject=None, frm=None, h_frm=None):
        GroupChat.__init__(self, to, body=body, subject=subject, frm=frm)
        d = self.addElement('delay', NS_DELAY)
        d['stamp'] = stamp
        if h_frm:
            d['from'] = h_frm



class HistoryOptions(object):
    """
        A history configuration object.

    @ivar maxchars: Limit the total number of characters in the history to "X"
                    (where the character count is the characters of the complete XML stanzas, not only their XML character data).
    @type maxchars: L{int}

    @ivar  maxstanzas: 	Limit the total number of messages in the history to "X".
    @type mazstanzas: L{int}

    @ivar  seconds: Send only the messages received in the last "X" seconds.
    @type seconds: L{int}

    @ivar  since: Send only the messages received since the datetime specified (which MUST conform to the DateTime profile specified in XMPP Date and Time Profiles [14]).
    @type since: L{datetime.datetime}
    """
    attributes = ['maxchars', 'maxstanzas', 'seconds', 'since']

    def __init__(self, maxchars=None, maxstanzas=None, seconds=None, since=None):
        self.maxchars = maxchars
        self.maxstanzas = maxstanzas
        self.seconds = seconds
        self.since = since


    def toElement(self):
        """
        Returns a L{domish.Element} representing the xml for the history options.
        """
        h = domish.Element((None, 'history'))
        for key in self.attributes:
            a = getattr(self, key, None)
            if a is not None:
                if key == 'since':
                    h[key] = a.strftime('%Y%m%dT%H:%M:%S')
                else:
                    h[key] = str(a)

        return h



class User(object):
    """
    A user/entity in a multi-user chat room.
    """

    def __init__(self, nick, entity=None):
        self.nick = nick
        self.entity = entity
        self.affiliation = 'none'
        self.role = 'none'

        self.status = None
        self.show = None



class Room(object):
    """
    A Multi User Chat Room. An in memory object representing a MUC room.
    """


    def __init__(self, roomIdentifier, service, nick, state=None):
        """
        Initialize the room.

        @ivar roomIdentifier: The Room ID of the MUC room.
        @type roomIdentifier: C{unicode}

        @ivar service: The server where the MUC room is located.
        @type service: C{unicode}

        @ivar nick: The nick name for the client in this room.
        @type nick: C{unicode}

        @ivar state: The status code of the room.
        @type state: L{int}

        @ivar occupantJID: The JID of the occupant in the room. Generated from roomIdentifier, service, and nick.
        @type occupantJID: L{jid.JID}
        """
        self.state = state
        self.roomIdentifier = roomIdentifier
        self.service = service
        self.nick = nick
        self.status = 0

        self.occupantJID = self.refreshOccupantJID()

        self.roster = {}


    def refreshOccupantJID(self):
        """
        Refreshes the Room JID.

        This method should be called whenever roomIdentifier, service, or nick
        change.
        """
        self.occupantJID = jid.internJID(u"%s@%s/%s" % (self.roomIdentifier,
                                                    self.service,
                                                    self.nick))
        return self.occupantJID


    def addUser(self, user):
        """
        Add a user to the room roster.

        @param user: The user object that is being added to the room.
        @type user: L{User}
        """
        self.roster[user.nick.lower()] = user


    def inRoster(self, user):
        """
        Check if a user is in the MUC room.

        @param user: The user object to check.
        @type user: L{User}
        """

        return self.roster.has_key(user.nick.lower())


    def getUser(self, nick):
        """
        Get a user from the room's roster.

        @param nick: The nick for the user in the MUC room.
        @type nick: C{unicode}
        """
        return self.roster.get(nick.lower())


    def removeUser(self, user):
        """
        Remove a user from the MUC room's roster.

        @param user: The user object to check.
        @type user: L{User}
        """
        if self.inRoster(user):
            del self.roster[user.nick.lower()]



class BasicPresence(xmppim.AvailablePresence):
    """
    This behaves like an object providing L{domish.IElement}.
    """

    def __init__(self, to=None, show=None, statuses=None):
        xmppim.AvailablePresence.__init__(self, to=to, show=show, statuses=statuses)
        # add muc elements
        x = self.addElement('x', NS_MUC)



class UserPresence(xmppim.Presence):
    """
    This behaves like an object providing L{domish.IElement}.
    """

    def __init__(self, to=None, type=None, frm=None, affiliation=None, role=None):
        xmppim.Presence.__init__(self, to, type)
        if frm:
            self['from'] = frm
        # add muc elements
        x = self.addElement('x', NS_MUC_USER)
        if affiliation:
            x['affiliation'] = affiliation
        if role:
            x['role'] = role



class UnavailableUserPresence(xmppim.UnavailablePresence):
    """
    This behaves like an object providing L{domish.IElement}.
    """

    def __init__(self, to=None, type=None, frm=None, affiliation=None, role=None):
        xmppim.UnavailablePresence.__init__(self, to, type)
        if frm:
            self['from'] = frm
        # add muc elements
        x = self.addElement('x', NS_MUC_USER)
        if affiliation:
            x['affiliation'] = affiliation
        if role:
            x['role'] = role



class PasswordPresence(BasicPresence):
    """
        This behaves like an object providing L{domish.IElement}.
    """
    def __init__(self, to, password):
        BasicPresence.__init__(self, to)

        self.x.addElement('password', None, password)



class MessageVoice(GroupChat):
    """
        This behaves like an object providing L{domish.IElement}.
    """
    def __init__(self, to=None, frm=None):
        GroupChat.__init__(self, to=to, frm=frm)
        # build data form
        form = data_form.Form('submit', formNamespace=NS_MUC_REQUEST)
        form.addField(data_form.Field(var='muc#role',
                                      value='participant',
                                      label='Requested role'))
        self.addChild(form.toElement())



class PresenceError(xmppim.Presence):
    """
    This behaves like an object providing L{domish.IElement}.
    """

    def __init__(self, error, to=None, frm=None):
        xmppim.Presence.__init__(self, to, type='error')
        if frm:
            self['from'] = frm
        # add muc elements
        x = self.addElement('x', NS_MUC)

        # add error
        e = error.getElement()
        self.addChild(e)



class MUCClient(XMPPHandler):
    """
    Multi-User Chat client protocol.

    This is a subclass of L{XMPPHandler} and implements L{IMUCCLient}.

    @ivar _rooms: Collection of occupied rooms, keyed by the bare JID of the
                  room. Note that a particular entity can only join a room once
                  at a time.
    @type _rooms: C{dict}
    """

    implements(IMUCClient)

    timeout = None

    def __init__(self):
        XMPPHandler.__init__(self)

        self._rooms = {}
        self._deferreds = []


    def connectionInitialized(self):
        """
        This method is called when the client has successfully authenticated.
        It initializes several xpath events to handle MUC stanzas that come in.
        After those are initialized then the method initialized is called to signal that we have finished.
        """
        self.xmlstream.addObserver(PRESENCE+"[not(@type) or @type='available']/x", self._onXPresence)
        self.xmlstream.addObserver(PRESENCE+"[@type='unavailable']", self._onUnavailablePresence)
        self.xmlstream.addObserver(PRESENCE+"[@type='error']", self._onPresenceError)
        self.xmlstream.addObserver(GROUPCHAT, self._onGroupChat)
        self.xmlstream.addObserver(SUBJECT, self._onSubject)
        # add history

        self.initialized()


    def _addRoom(self, room):
        """
        Add a room to the room collection.

        Rooms are stored by the JID of the room itself. I.e. it uses the Room
        ID and service parts of the Room JID.

        @note: An entity can only join a particular room once.
        """
        roomJID = room.occupantJID.userhostJID()
        self._rooms[roomJID] = room


    def _getRoom(self, occupantJID):
        """
        Grab a room from the room collection.

        This uses the Room ID and service parts of the given JID to look up
        the L{Room} instance associated with it.
        """
        roomJID = occupantJID.userhostJID()
        return self._rooms.get(roomJID)


    def _removeRoom(self, occupantJID):
        """
        Delete a room from the room collection.
        """
        roomJID = occupantJID.userhostJID()
        if roomJID in self._rooms:
            del self._rooms[roomJID]


    def _onUnavailablePresence(self, prs):
        """
        This method is called when the stanza matches the xpath observer.
        The client has received a presence stanza with the 'type' attribute of unavailable.
        It means a user has exited a MUC room.
        """

        if not prs.hasAttribute('from'):
            return
        occupantJID = jid.internJID(prs.getAttribute('from', ''))
        self._userLeavesRoom(occupantJID)


    def _onPresenceError(self, prs):
        """
        This method is called when a presence stanza with the 'type' attribute of error.
        There are various reasons for receiving a presence error and it means that the user has left the room.
        """
        if not prs.hasAttribute('from'):
            return
        occupantJID = jid.internJID(prs.getAttribute('from', ''))
        # add an error hook here?
        self._userLeavesRoom(occupantJID)


    def _getExceptionFromElement(self, stanza):
        # find an exception based on the error stanza
        muc_condition = 'exception'

        error = getattr(stanza, 'error', None)
        if error is not None:
            for e in error.elements():
                muc_condition = e.name

        return MUC_EXCEPTIONS[muc_condition]


    def _userLeavesRoom(self, occupantJID):
        # when a user leaves a room we need to update it
        room = self._getRoom(occupantJID)
        if room is None:
            # not in the room yet
            return
        # check if user is in roster
        user = room.getUser(occupantJID.resource)
        if user is None:
            return
        if room.inRoster(user):
            room.removeUser(user)
            self.userLeftRoom(room, user)


    def _onXPresence(self, prs):
        """
        A muc presence has been received.
        """
        if not prs.hasAttribute('from'):
            return
        occupantJID = jid.internJID(prs.getAttribute('from', ''))

        status = getattr(prs, 'status', None)
        show = getattr(prs, 'show', None)

        # grab room
        room = self._getRoom(occupantJID)
        if room is None:
            # not in the room yet
            return
        user = self._changeUserStatus(room, occupantJID, status, show)

        if room.inRoster(user):
            # we changed status or nick
            muc_status = getattr(prs.x, 'status', None)
            if muc_status:
                code = muc_status.getAttribute('code', 0)
            else:
                self.userUpdatedStatus(room, user, show, status)
        else:
            room.addUser(user)
            self.userJoinedRoom(room, user)


    def _onGroupChat(self, msg):
        """
        A group chat message has been received from a MUC room.

        There are a few event methods that may get called here. receviedGroupChat and receivedHistory
        """
        if not msg.hasAttribute('from'):
            # need to return an error here
            return
        occupantJID = jid.internJID(msg.getAttribute('from', ''))

        room = self._getRoom(occupantJID)
        if room is None:
            # not in the room yet
            return
        user = room.getUser(occupantJID.resource)
        delay = None
        # need to check for delay and x stanzas for delay namespace for backwards compatability
        for e in msg.elements():
            if e.uri == NS_DELAY or e.uri == NS_JABBER_DELAY:
                delay = e
        body = unicode(msg.body)
        # grab room
        if delay is None:
            self.receivedGroupChat(room, user, body)
        else:
            self.receivedHistory(room, user, body, delay['stamp'], frm=delay.getAttribute('from',None))


    def _onSubject(self, msg):
        """
        A subject has been sent from a MUC room.
        """
        if not msg.hasAttribute('from'):
            return
        occupantJID = jid.internJID(msg['from'])

        # grab room
        room = self._getRoom(occupantJID)
        if room is None:
            # not in the room yet
            return

        self.receivedSubject(occupantJID, unicode(msg.subject))


    def _makeTimeStamp(self, stamp=None):
        # create a timestamp
        if stamp is None:
            stamp = datetime.datetime.now()

        return stamp.strftime('%Y%m%dT%H:%M:%S')


    def _joinedRoom(self, d, prs):
        """
        We have presence that says we joined a room.
        """
        occupantJID = jid.internJID(prs['from'])

        # check for errors
        if prs.hasAttribute('type') and prs['type'] == 'error':
            d.errback(self._getExceptionFromElement(prs))
        else:
            # change the state of the room
            room = self._getRoom(occupantJID)
            if room is None:
                raise NotFound
            room.state = 'joined'

            # grab status
            status = getattr(prs.x, 'status', None)
            if status:
                room.status = status.getAttribute('code', None)

            d.callback(room)


    def _leftRoom(self, d, prs):
        """
        We have presence that says we left a room.
        """
        occupantJID = jid.internJID(prs['from'])

        # check for errors
        if prs.hasAttribute('type') and prs['type'] == 'error':
            d.errback(self._getExceptionFromElement(prs))
        else:
            # change the state of the room
            room = self._getRoom(occupantJID)
            if room is None:
                raise NotFound
            self._removeRoom(occupantJID)

            d.callback(True)


    def initialized(self):
        """
        Client is initialized and ready!
        """
        pass


    def userJoinedRoom(self, room, user):
        """
        User has joined a MUC room.

        This method will need to be modified inorder for clients to
        do something when this event occurs.

        @param room: The room the user has joined.
        @type room: L{Room}

        @param user: The user that joined the MUC room.
        @type user: L{User}
        """
        pass


    def userLeftRoom(self, room, user):
        """
        User has left a room.

        This method will need to be modified inorder for clients to
        do something when this event occurs.

        @param room: The room the user has joined.
        @type room: L{Room}

        @param user: The user that joined the MUC room.
        @type user: L{User}
        """
        pass


    def userUpdatedStatus(self, room, user, show, status):
        """
        User Presence has been received.

        This method will need to be modified inorder for clients to
        do something when this event occurs.
        """
        pass


    def receivedSubject(self, room, subject):
        """
        This method will need to be modified inorder for clients to
        do something when this event occurs.
        """
        pass


    def receivedHistory(self, room, user, message, history, frm=None):
        """
        This method will need to be modified inorder for clients to
        do something when this event occurs.
        """
        pass


    def _cbDisco(self, iq):
        # grab query

        return getattr(iq,'query', None)


    def sendDeferred(self,  obj, timeout):
        """
        Send data or a domish element, adding a deferred with a timeout.

        @param obj: The object to send over the wire.
        @type obj: L{domish.Element} or C{unicode}

        @param timeout: The number of seconds to wait before the deferred is timed out.
        @type timeout: L{int}

        The deferred object L{defer.Deferred} is returned.
        """
        d = defer.Deferred()
        self._deferreds.append(d)


        def onTimeout():
            i = 0
            for xd in self._deferreds:
                if d == xd:
                    self._deferreds.pop(i)
                    d.errback(xmlstream.TimeoutError("Timeout waiting for response."))
                i += 1

        call = reactor.callLater(timeout, onTimeout)

        def cancelTimeout(result):
            if call.active():
                call.cancel()

            return result

        d.addBoth(cancelTimeout)

        self.xmlstream.send(obj)
        return d


    def configure(self, roomJID, fields=[]):
        """
        Configure a room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param fields: The fields we want to modify.
        @type fields: A L{list} or L{dataform.Field}
        """
        request = ConfigureRequest(self.xmlstream, method='set', fields=fields)
        request['to'] = roomJID

        return request.send()


    def getConfigureForm(self, roomJID):
        """
        Grab the configuration form from the room. This sends an iq request to the room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}
        """
        request = ConfigureRequest(self.xmlstream)
        request['to'] = roomJID
        return request.send()


    def join(self, service, roomIdentifier, nick, history=None):
        """
        Join a MUC room by sending presence to it.

        @param server: The server where the room is located.
        @type server: C{unicode}

        @param room: The room name the entity is joining.
        @type room: C{unicode}

        @param nick: The nick name for the entitity joining the room.
        @type nick: C{unicode}

        @param history: The maximum number of history stanzas you would like.

        @return: A deferred that fires when the entity is in the room or an
                 error has occurred.
        """
        room = Room(roomIdentifier, service, nick, state='joining')
        self._addRoom(room)

        p = BasicPresence(to=room.occupantJID)
        if history is not None:
            p.x.addChild(history.toElement())

        d = self.sendDeferred(p, timeout=DEFER_TIMEOUT)

        # add observer for joining the room
        query = PRESENCE + u"[@from='%s']" % room.occupantJID
        self.xmlstream.addOnetimeObserver(query, self._joinedRoom, 1, d)

        return d


    def _changeUserStatus(self, room, occupantJID, status, show):
        """
        Change the user status in a room.
        """

        # check if user is in roster
        user = room.getUser(occupantJID.resource)
        if user is None: # create a user that does not exist
            user = User(occupantJID.resource)

        if status is not None:
            user.status = unicode(status)
        if show is not None:
            user.show = unicode(show)

        return user


    def _changed(self, d, occupantJID, prs):
        """
        Callback for changing the nick and status.
        """

        status = getattr(prs, 'status', None)
        show = getattr(prs, 'show', None)

        room = self._getRoom(occupantJID)

        user = self._changeUserStatus(room, occupantJID, status, show)

        d.callback(room)


    def nick(self, roomJID, new_nick):
        """
        Change an entities nick name in a MUC room.

        See: http://xmpp.org/extensions/xep-0045.html#changenick

        @param roomJID: The JID of the room, i.e. without a resource.
        @type roomJID: L{jid.JID}

        @param new_nick: The nick name for the entitity joining the room.
        @type new_nick: C{unicode}
        """


        room = self._getRoom(roomJID)
        if room is None:
            raise NotFound

        # Change the nickname
        room.nick = new_nick
        room.refreshOccupantJID()

        # Create presence
        p = BasicPresence(to=room.occupantJID)
        d = self.sendDeferred(p, timeout=DEFER_TIMEOUT)

        # Add observer for joining the room
        query = PRESENCE+"[@from='%s']" % (room.occupantJID.full())
        self.xmlstream.addOnetimeObserver(query, self._changed, 1, d, roomJID)

        return d


    def leave(self, occupantJID):
        """
        Leave a MUC room.

        See: http://xmpp.org/extensions/xep-0045.html#exit

        @param occupantJID: The Room JID of the room to leave.
        @type occupantJID: L{jid.JID}
        """
        room = self._getRoom(occupantJID)

        p = xmppim.UnavailablePresence(to=room.occupantJID)

        d = self.sendDeferred(p, timeout=DEFER_TIMEOUT)
        # add observer for joining the room
        query = PRESENCE + u"[@from='%s' and @type='unavailable']" % (room.occupantJID)
        self.xmlstream.addOnetimeObserver(query, self._leftRoom, 1, d)

        return d


    def status(self, occupantJID, show=None, status=None):
        """
        Change user status.

        See: http://xmpp.org/extensions/xep-0045.html#changepres

        @param occupantJID: The room jabber/xmpp entity id for the requested configuration form.
        @type occupantJID: L{jid.JID}

        @param show: The availability of the entity. Common values are xa, available, etc
        @type show: C{unicode}

        @param show: The current status of the entity.
        @type show: C{unicode}
        """
        room = self._getRoom(occupantJID)
        if room is None:
            raise NotFound

        p = BasicPresence(to=room.occupantJID)
        if status is not None:
            p.addElement('status', None, status)

        if show is not None:
            p.addElement('show', None, show)

        d = self.sendDeferred(p, timeout=DEFER_TIMEOUT)

        # add observer for joining the room
        query = PRESENCE + u"[@from='%s']" % room.occupantJID
        self.xmlstream.addOnetimeObserver(query, self._changed, 1, d, occupantJID)

        return d


    def _sendMessage(self, msg, children=None):
        """
        Send a message.
        """
        if children:
            for child in children:
                msg.addChild(child)

        self.xmlstream.send(msg)


    def groupChat(self, to, message, children=None):
        """
        Send a groupchat message.
        """
        msg = GroupChat(to, body=message)

        self._sendMessage(msg, children=children)


    def chat(self, occupantJID, message, children=None):
        """
        Send a private chat message to a user in a MUC room.

        See: http://xmpp.org/extensions/xep-0045.html#privatemessage

        @param occupantJID: The Room JID of the other user.
        @type occupantJID: L{jid.JID}
        """

        msg = PrivateChat(occupantJID, body=message)

        self._sendMessage(msg, children=children)


    def invite(self, roomJID, reason=None, invitee=None):
        """
        Invite a xmpp entity to a MUC room.

        See: http://xmpp.org/extensions/xep-0045.html#invite

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param reason: The reason for the invite.
        @type reason: C{unicode}

        @param invitee: The entity that is being invited.
        @type invitee: L{jid.JID}
        """
        msg = InviteMessage(roomJID, reason=reason, invitee=invitee)
        self._sendMessage(msg)


    def password(self, roomJID, password):
        """
        Send a password to a room so the entity can join.

        See: http://xmpp.org/extensions/xep-0045.html#enter-pw

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param password: The MUC room password.
        @type password: C{unicode}
        """
        p = PasswordPresence(roomJID, password)

        self.xmlstream.send(p)


    def register(self, roomJID, fields=[]):
        """
        Send a request to register for a room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param fields: The fields you need to register.
        @type fields: L{list} of L{dataform.Field}
        """
        iq = RegisterRequest(self.xmlstream, method='set', fields=fields)
        iq['to'] = roomJID.userhost()
        return iq.send()


    def _getAffiliationList(self, roomJID, affiliation):
        """
        Send a request for an affiliation list in a room.
        """
        iq = AffiliationRequest(self.xmlstream,
                                method='get',
                                affiliation=affiliation,
                                )
        iq['to'] = roomJID.userhost()
        return iq.send()


    def _getRoleList(self, roomJID, role):
        """
        Send a role request.
        """
        iq = RoleRequest(self.xmlstream,
                         method='get',
                         role=role,
                         )
        iq['to'] = roomJID.full()
        return iq.send()


    def _setAffiliationList(self, iq, affiliation, occupantJID):
        # set a rooms affiliation list
        room = self._getRoom(occupantJID)
        if room is not None:
            affiliation_list = []
            setattr(room, affiliation, [])

            for item in iq.query.elements():
                nick = item.getAttribute('nick', None)
                entity = item.getAttribute('jid', None)
                role = item.getAttribute('role', None)
                user = None
                if nick is None and entity is None:
                    raise Exception, 'bad attributes in item list'
                if nick is not None:
                    user = room.getUser(nick)
                if user is None:
                    user = User(nick, entity=jid.internJID(entity))
                    user.affiliation = 'member'
                if role is not None:
                    user.role = role

                affiliation_list.append(user)

            setattr(room, affiliation, affiliation_list)
        return room


    def getMemberList(self, roomJID):
        """
        Get the member list of a room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}
        """
        d = self._getAffiliationList(roomJID, 'member')
        d.addCallback(self._setAffiliationList, 'members', roomJID)
        return d


    def getAdminList(self, roomJID):
        """
        Get the admin list of a room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}
        """
        d = self._getAffiliationList(roomJID, 'admin')
        d.addCallback(self._setAffiliationList, 'admin', roomJID)
        return d


    def getBanList(self, roomJID):
        """
        Get an outcast list from a room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}
        """
        d = self._getAffiliationList(roomJID, 'outcast')
        d.addCallback(self._setAffiliationList, 'outcast', roomJID)
        return d


    def getOwnerList(self, roomJID):
        """
        Get an owner list from a room.

        @param roomJID: The room jabber/xmpp entity id for the requested member list.
        @type roomJID: L{jid.JID}
        """
        d = self._getAffiliationList(roomJID, 'owner')
        d.addCallback(self._setAffiliationList, 'owner', roomJID)
        return d


    def getRegisterForm(self, room):
        """
        Grab the registration form for a MUC room.

        @param room: The room jabber/xmpp entity id for the requested registration form.
        @type room: L{jid.JID}
        """
        iq = RegisterRequest(self.xmlstream)
        iq['to'] = room.userhost()
        return iq.send()


    def destroy(self, roomJID, reason=None, alternate=None):
        """
        Destroy a room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param reason: The reason we are destroying the room.
        @type reason: C{unicode}

        @param alternate: The bare JID of the room suggested as an alternate
                          venue.
        @type alternate: L{jid.JID}

        """
        def destroyed(iq):
            self._removeRoom(roomJID)
            return True

        iq = OwnerRequest(self.xmlstream, method='set')
        iq['to'] = roomJID.userhost()
        d = iq.query.addElement('destroy')

        if alternate is not None:
            d['jid'] = alternate.userhost()
        if reason is not None:
            d.addElement('reason', None, reason)

        return iq.send().addCallback(destroyed)


    def subject(self, roomJID, subject):
        """
        Change the subject of a MUC room.

        See: http://xmpp.org/extensions/xep-0045.html#subject-mod

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param subject: The subject you want to set.
        @type subject: C{unicode}
        """
        msg = GroupChat(roomJID.userhostJID(), subject=subject)
        self.xmlstream.send(msg)


    def voice(self, roomJID):
        """
        Request voice for a moderated room.

        @param roomJID: The room jabber/xmpp entity id.
        @type roomJID: L{jid.JID}
        """
        msg = MessageVoice(to=roomJID.userhostJID())
        self.xmlstream.send(msg)


    def history(self, roomJID, messages):
        """
        Send history to create a MUC based on a one on one chat.

        See: http://xmpp.org/extensions/xep-0045.html#continue

        @param roomJID: The room jabber/xmpp entity id.
        @type roomJID: L{jid.JID}

        @param messages: The history to send to the room as an ordered list of
                         message, represented by a dictionary with the keys
                         C{'stanza'}, holding the original stanza a
                         L{domish.Element}, and C{'timestamp'} with the
                         timestamp.
        @type messages: L{list} of L{domish.Element}
        """

        for message in messages:
            stanza = message['stanza']
            stanza['type'] = 'groupchat'

            delay = stanza.addElement('delay', NS_DELAY)
            delay['stamp'] = message['timestamp']

            sender = stanza.getAttribute('from', None)
            if sender is not None:
                delay['from'] = sender

            stanza['to'] = roomJID.userhost()
            if stanza.hasAttribute('from'):
                del stanza['from']

            self.xmlstream.send(stanza)


    def _setAffiliation(self, roomJID, entityOrNick, affiliation,
                              reason=None, sender=None):
        """
        Send a request to change an entity's affiliation to a MUC room.
        """
        iq = AffiliationRequest(self.xmlstream,
                                method='set',
                                entityOrNick=entityOrNick,
                                affiliation=affiliation,
                                reason=reason)
        iq['to'] = roomJID.userhost()
        if sender is not None:
            iq['from'] = unicode(sender)

        return iq.send()


    def _setRole(self, roomJID, entityOrNick, role,
                       reason=None, sender=None):
        # send a role request
        iq = RoleRequest(self.xmlstream,
                         method='set',
                         role=role,
                         entityOrNick=entityOrNick,
                         reason=reason)

        iq['to'] = roomJID.userhost()
        if sender is not None:
            iq['from'] = unicode(sender)
        return iq.send()


    def modifyAffiliationList(self, frm, roomJID, jid_list, affiliation):
        """
        Modify an affiliation list.

        @param frm: The entity sending the request.
        @type frm: L{jid.JID}

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param entities: The list of entities to change in a room. This can be
            a nick or a full jid.
        @type jid_list: L{list} of C{unicode} for nicks. L{list} of L{jid.JID}
            for jids.

        @param affiliation: The affilation to change.
        @type affiliation: C{unicode}

        """
        iq = AffiliationRequest(self.xmlstream,
                                method='set',
                                affiliation=affiliation,
                                )
        iq.items(jid_list)
        iq['to'] = roomJID.userhost()
        iq['from'] = frm.full()
        return iq.send()


    def grantVoice(self, roomJID, nick, reason=None, sender=None):
        """
        Grant voice to an entity.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param nick: The nick name for the user in this room.
        @type nick: C{unicode}

        @param reason: The reason for granting voice to the entity.
        @type reason: C{unicode}

        @param sender: The entity sending the request.
        @type sender: L{jid.JID}
        """
        return self._setRole(roomJID, entityOrNick=nick,
                             role='participant',
                             reason=reason, sender=sender)


    def revokeVoice(self, roomJID, nick, reason=None, sender=None):
        """
        Revoke voice from a participant.

        This will disallow the entity to send messages to a moderated room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param nick: The nick name for the user in this room.
        @type nick: C{unicode}

        @param reason: The reason for revoking voice from the entity.
        @type reason: C{unicode}

        @param sender: The entity sending the request.
        @type sender: L{jid.JID}
        """
        return self._setRole(roomJID, entityOrNick=nick, role='visitor',
                             reason=reason, sender=sender)


    def grantModerator(self, roomJID, nick, reason=None, sender=None):
        """
        Grant moderator priviledges to a MUC room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param nick: The nick name for the user in this room.
        @type nick: C{unicode}

        @param reason: The reason for granting moderation to the entity.
        @type reason: C{unicode}

        @param sender: The entity sending the request.
        @type sender: L{jid.JID}
        """
        return self._setRole(roomJID, entityOrNick=nick, role='moderator',
                             reason=reason, sender=sender)


    def ban(self, roomJID, entity, reason=None, sender=None):
        """
        Ban a user from a MUC room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param entity: The room jabber/xmpp entity id.
        @type entity: L{jid.JID}

        @param reason: The reason for banning the entity.
        @type reason: C{unicode}

        @param sender: The entity sending the request.
        @type sender: L{jid.JID}
        """
        return self._setAffiliation(roomJID, entity, 'outcast',
                                    reason=reason, sender=sender)


    def kick(self, roomJID, entityOrNick, reason=None, sender=None):
        """
        Kick a user from a MUC room.

        @param roomJID: The bare JID of the room.
        @type roomJID: L{jid.JID}

        @param entityOrNick: The occupant to be banned.
        @type entityOrNick: L{jid.JID} or C{unicode}

        @param reason: The reason given for the kick.
        @type reason: C{unicode}

        @param sender: The entity sending the request.
        @type sender: L{jid.JID}
        """
        return self._setAffiliation(roomJID, entityOrNick, 'none',
                                    reason=reason, sender=sender)
