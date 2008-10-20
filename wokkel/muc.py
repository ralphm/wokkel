# -*- test-case-name: wokkel.test.test_muc -*-
#
# Copyright (c) 2003-2008 Ralph Meijer
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

from wokkel import disco, data_form, shim, xmppim
from wokkel.subprotocols import IQHandlerMixin, XMPPHandler
from wokkel.iwokkel import IMUCClient

# Multi User Chat namespaces
NS_MUC          = 'http://jabber.org/protocol/muc'
NS_MUC_USER     = NS_MUC + '#user'
NS_MUC_ADMIN    = NS_MUC + '#admin'
NS_MUC_OWNER    = NS_MUC + '#owner'
NS_MUC_ROOMINFO = NS_MUC + '#roominfo'
NS_MUC_CONFIG   = NS_MUC + '#roomconfig'
NS_MUC_REQUEST  = NS_MUC + '#request'
NS_MUC_REGISTER = NS_MUC + '#register'

NS_DELAY        = 'urn:xmpp:delay'
NS_JABBER_DELAY = 'jabber:x:delay'

NS_REQUEST  = 'jabber:iq:register'

# ad hoc commands
NS_AD_HOC       = "http://jabber.org/protocol/commands"


# Iq get and set XPath queries
IQ     = '/iq'
IQ_GET = IQ+'[@type="get"]'
IQ_SET = IQ+'[@type="set"]'

IQ_RESULT = IQ+'[@type="result"]'
IQ_ERROR  = IQ+'[@type="error"]'

IQ_QUERY     = IQ+'/query'
IQ_GET_QUERY = IQ_GET + '/query'
IQ_SET_QUERY = IQ_SET + '/query'

IQ_COMMAND   = IQ+'/command'

MUC_ADMIN = IQ_QUERY+'[@xmlns="' + NS_MUC_ADMIN + '"]'
MUC_OWNER = IQ_QUERY+'[@xmlns="' + NS_MUC_OWNER + '"]'

MUC_AO = MUC_ADMIN + '|' + MUC_OWNER


MESSAGE  = '/message'
PRESENCE = '/presence'

CHAT_BODY = MESSAGE +'[@type="chat"]/body'
CHAT      = MESSAGE +'[@type="chat"]'

GROUPCHAT     = MESSAGE +'[@type="groupchat"]/body'
SUBJECT       = MESSAGE +'[@type="groupchat"]/subject'
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
    condition    = 'modify'
    mucCondition = 'jid-malformed'
    
class NotAuthorized(Exception):
    """
    """
    condition    = 'auth'
    mucCondition = 'not-authorized'

class RegistrationRequired(Exception):
    """
    """
    condition    = 'auth'
    mucCondition = 'registration-required'


class Forbidden(Exception):
    """
    """
    condition    = 'auth'
    mucCondition = 'forbidden'

class Conflict(Exception):
    """
    """
    condition    = 'cancel'
    mucCondition = 'conflict'

class NotFound(Exception):
    """
    """
    condition    = 'cancel'
    mucCondition = 'not-found'

class ServiceUnavailable(Exception):
    """
    """
    condition    = 'wait'
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
    A basic admin iq request 

    @ivar method: Type attribute of the IQ request. Either C{'set'} or C{'get'}
    @type method: C{str}

    """

    def __init__(self, xs, method='get'):
        xmlstream.IQ.__init__(self, xs, method)
        q = self.addElement((NS_MUC_ADMIN, 'query'))


class OwnerRequest(xmlstream.IQ):
    """
    A basic owner iq request 

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

    def __init__(self, xs, method='get', affiliation='none', a_jid=None, reason=None):
        AdminRequest.__init__(self, xs, method)

        i = self.query.addElement('item')

        i['affiliation'] = affiliation
        if a_jid:
            i['jid'] = a_jid.full()
            
        if reason:
            i.addElement('reason', None, reason)

            
class RoleRequest(AdminRequest):
    def __init__(self, xs, method='get', role='none', a_jid=None, reason=None):
        AdminRequest.__init__(self, xs, method)

        i = self.query.addElement('item')

        i['role'] = role
        if a_jid:
            i['jid'] = a_jid.full()
            
        if reason:
            i.addElement('reason', None, reason)

class GroupChat(domish.Element):
    """
    """
    def __init__(self, to, body=None, subject=None, frm=None):
        """To needs to be a string
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
    """
    def __init__(self, to, body=None, frm=None):
        """To needs to be a string
        """
        domish.Element.__init__(self, (None, 'message'))
        self['type'] = 'chat'
        self['to']   = to 
        if frm:
            self['from'] = frm
        if body:
            self.addElement('body',None, body)
            
class InviteMessage(PrivateChat):
    def __init__(self, to, reason=None, full_jid=None, body=None, frm=None, password=None):
        PrivateChat.__init__(self, to, body=body, frm=frm)
        del self['type'] # remove type
        x = self.addElement('x', NS_MUC_USER)
        invite = x.addElement('invite')
        if full_jid:
            invite['to'] = full_jid
        if reason:
            invite.addElement('reason', None, reason)
        if password:
            invite.addElement('password', None, password)

class HistoryMessage(GroupChat):
    """
    """
    def __init__(self, to, stamp, body=None, subject=None, frm=None, h_frm=None):
        GroupChat.__init__(self, to, body=body, subject=subject, frm=frm)
        d = self.addElement('delay', NS_DELAY)
        d['stamp'] = stamp
        if h_frm:
            d['from'] = h_frm

class HistoryOptions(object):
    """A history configuration object.

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
        self.maxchars   = maxchars
        self.maxstanzas = maxstanzas
        self.seconds    = seconds
        self.since      = since

    def toElement(self):
        h = domish.Element((None, 'history'))
        for key in self.attributes:
            a = getattr(self, key, a)
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
    
    def __init__(self, nick, user_jid=None):
        self.nick = nick
        self.user_jid = user_jid
        self.affiliation = 'none'
        self.role = 'none'
        
        self.status = None
        self.show   = None


class Room(object):
    """
    A Multi User Chat Room
    """

    
    def __init__(self, name, server, nick, state=None):
        """
        """
        self.state  = state
        self.name   = name
        self.server = server
        self.nick   = nick
        self.status = 0

        self.entity_id = self.entityId()
               
        self.roster = {}

    def entityId(self):
        """
        """
        self.entity_id = jid.internJID(self.name+'@'+self.server+'/'+self.nick)

        return self.entity_id 

    def addUser(self, user):
        """
        """
        self.roster[user.nick.lower()] = user

    def inRoster(self, user):
        """
        """

        return self.roster.has_key(user.nick.lower())

    def getUser(self, nick):
        """
        """
        return self.roster.get(nick.lower())

    def removeUser(self, user):
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
    """
    def __init__(self, to, password):
        BasicPresence.__init__(self, to)
        
        self.x.addElement('password', None, password)


class MessageVoice(GroupChat):
    """
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
    Multi-User chat client protocol. This is a subclass of L{XMPPHandler} and implements L{IMUCCLient}.

    """

    implements(IMUCClient)

    rooms = {}

    timeout = None

    _deferreds = []

    def connectionInitialized(self):
        """ This method is called when the client has successfully authenticated. 
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

    def _setRoom(self, room):
        """Add a room to the room collection.
        """
        self.rooms[room.entity_id.userhost().lower()] = room

    def _getRoom(self, room_jid):
        """Grab a room from the room collection.
        """
        return self.rooms.get(room_jid.userhost().lower())

    def _removeRoom(self, room_jid):
        """Delete a room from the room collection.
        """
        if self.rooms.has_key(room_jid.userhost().lower()):
            del self.rooms[room_jid.userhost().lower()]


    def _onUnavailablePresence(self, prs):
        """ This method is called when the stanza matches the xpath observer. 
        The client has received a presence stanza with the 'type' attribute of unavailable. 
        It means a user has exited a MUC room.
        """

        if not prs.hasAttribute('from'):
            return
        room_jid = jid.internJID(prs.getAttribute('from', ''))
        self._userLeavesRoom(room_jid)

    def _onPresenceError(self, prs):
        """This method is called when a presence stanza with the 'type' attribute of error.
        There are various reasons for receiving a presence error and it means that the user has left the room.
        """
        if not prs.hasAttribute('from'):
            return
        room_jid = jid.internJID(prs.getAttribute('from', ''))
        # add an error hook here?
        self._userLeavesRoom(room_jid)
        
    def _getExceptionFromElement(self, stanza):
        # find an exception based on the error stanza
        muc_condition = 'exception'

        error = getattr(stanza, 'error', None)
        if error is not None:
            for e in error.elements():
                muc_condition = e.name

        return MUC_EXCEPTIONS[muc_condition]

    def _userLeavesRoom(self, room_jid):
        # when a user leaves a room we need to update it
        room = self._getRoom(room_jid)
        if room is None:
            # not in the room yet
            return
        # check if user is in roster
        user = room.getUser(room_jid.resource)
        if user is None:
            return
        if room.inRoster(user):
            room.removeUser(user)
            self.userLeftRoom(room, user)
        
    def _onXPresence(self, prs):
        """ A muc presence has been received.
        """
        if not prs.hasAttribute('from'):
            return
        room_jid = jid.internJID(prs.getAttribute('from', ''))
            
        status = getattr(prs, 'status', None)
        show   = getattr(prs, 'show', None)
        
        # grab room
        room = self._getRoom(room_jid)
        if room is None:
            # not in the room yet
            return

        # check if user is in roster
        user = room.getUser(room_jid.resource)
        if user is None: # create a user that does not exist
            user = User(room_jid.resource)
            
        
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
        """
        if not msg.hasAttribute('from'):
            # need to return an error here
            return
        room_jid = jid.internJID(msg.getAttribute('from', ''))

        room = self._getRoom(room_jid)
        if room is None:
            # not in the room yet
            return
        user = room.getUser(room_jid.resource)
        delay = None
        # need to check for delay and x stanzas for delay namespace for backwards compatability
        for e in msg.elements():
            if e.uri == NS_DELAY or e.uri == NS_JABBER_DELAY:
                delay = e
        body  = unicode(msg.body)
        # grab room
        if delay is None:
            self.receivedGroupChat(room, user, body)
        else:
            self.receivedHistory(room, user, body, delay['stamp'], frm=delay.getAttribute('from',None))


    def _onSubject(self, msg):
        """
        """
        if not msg.hasAttribute('from'):
            return
        room_jid = jid.internJID(msg['from'])

        # grab room
        room = self._getRoom(room_jid)
        if room is None:
            # not in the room yet
            return

        self.receivedSubject(room_jid, unicode(msg.subject))


    def _makeTimeStamp(self, stamp=None):
        if stamp is None:
            stamp = datetime.datetime.now()
            
        return stamp.strftime('%Y%m%dT%H:%M:%S')


    def _joinedRoom(self, d, prs):
        """We have presence that says we joined a room.
        """
        room_jid = jid.internJID(prs['from'])
        
        # check for errors
        if prs.hasAttribute('type') and prs['type'] == 'error':            
            d.errback(self._getExceptionFromElement(prs))
        else:    
            # change the state of the room
            r = self._getRoom(room_jid)
            if r is None:
                raise NotFound
            r.state = 'joined'
            
            # grab status
            status = getattr(prs.x,'status',None)
            if status:
                r.status = status.getAttribute('code', None)

            d.callback(r)


    def _leftRoom(self, d, prs):
        """We have presence that says we joined a room.
        """
        room_jid = jid.internJID(prs['from'])
        
        # check for errors
        if prs.hasAttribute('type') and prs['type'] == 'error':            
            d.errback(self._getExceptionFromElement(prs))
        else:    
            # change the state of the room
            r = self._getRoom(room_jid)
            if r is None:
                raise NotFound
            self._removeRoom(room_jid)
            
            d.callback(True)

    def initialized(self):
        """Client is initialized and ready!
        """
        pass

    def userJoinedRoom(self, room, user):
        """User has joined a room
        """
        pass

    def userLeftRoom(self, room, user):
        """User has left a room
        """
        pass


    def userUpdatedStatus(self, room, user, show, status):
        """User Presence has been received
        """
        pass
        

    def receivedSubject(self, room, subject):
        """
        """
        pass


    def receivedHistory(self, room, user, message, history, frm=None):
        """
        """
        pass


    def _cbDisco(self, iq):
        # grab query
        
        return getattr(iq,'query', None)
        

    def sendDeferred(self,  obj, timeout):
        """ Send data or a domish element, adding a deferred with a timeout.
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

    def disco(self, entity, type='info'):
        """Send disco queries to a XMPP entity
        """

        iq = disco.DiscoRequest(self.xmlstream, disco.NS_INFO, 'get')
        iq['to'] = entity

        return iq.send().addBoth(self._cbDisco)
        

    def configure(self, room_jid, fields=[]):
        """Configure a room

        @param room_jid: The room jabber/xmpp entity id for the requested configuration form.
        @type  room_jid: L{jid.JID}

        """
        request = ConfigureRequest(self.xmlstream, method='set', fields=fields)
        request['to'] = room_jid
        
        return request.send()

    def getConfigureForm(self, room_jid):
        """Grab the configuration form from the room. This sends an iq request to the room.

        @param room_jid: The room jabber/xmpp entity id for the requested configuration form.
        @type  room_jid: L{jid.JID}

        """
        request = ConfigureRequest(self.xmlstream)
        request['to'] = room_jid
        return request.send()


    def join(self, server, room, nick, history = None):
        """ Join a MUC room by sending presence to it. Returns a defered that is called when
        the entity is in the room or an error has occurred. 
        
        @param server: The server where the room is located.
        @type  server: L{unicode}

        @param room: The room name the entity is joining.
        @type  room: L{unicode}

        @param nick: The nick name for the entitity joining the room.
        @type  nick: L{unicode}
        
        @param history: The maximum number of history stanzas you would like.

        """
        r = Room(room, server, nick, state='joining')
        self._setRoom(r)
 
        p = BasicPresence(to=r.entity_id)
        if history is not None:
            p.x.addChild(history.toElement())

        d = self.sendDeferred(p, timeout=DEFER_TIMEOUT)

        # add observer for joining the room
        self.xmlstream.addOnetimeObserver(PRESENCE+"[@from='%s']" % (r.entity_id.full()), 
                                          self._joinedRoom, 1, d)

        return d
    
    def _changed(self, d, room_jid, prs):
        """Callback for changing the nick and status.
        """

        r = self._getRoom(room_jid)

        d.callback(r)


    def nick(self, room_jid, new_nick):
        """ Change an entities nick name in a MUC room. 
        
        See: http://xmpp.org/extensions/xep-0045.html#changenick

        @param room_jid: The room jabber/xmpp entity id for the requested configuration form.
        @type  room_jid: L{jid.JID}

        @param new_nick: The nick name for the entitity joining the room.
        @type  new_nick: L{unicode}
        
        """

        
        r = self._getRoom(room_jid)
        if r is None:
            raise NotFound
        r.nick = new_nick # change the nick
        # create presence 
        # make sure we call the method to generate the new entity xmpp id
        p = BasicPresence(to=r.entityId()) 
        d = self.sendDeferred(p, timeout=DEFER_TIMEOUT)

        # add observer for joining the room
        self.xmlstream.addOnetimeObserver(PRESENCE+"[@from='%s']" % (r.entity_id.full()), 
                                          self._changed, 1, d, room_jid)

        return d
        

    
    def leave(self, room_jid):
        """Leave a MUC room.

        See: http://xmpp.org/extensions/xep-0045.html#exit

        @param room_jid: The room entity id you want to exit.
        @type  room_jid: L{jid.JID}

        """
        r = self._getRoom(room_jid)
 
        p = xmppim.UnavailablePresence(to=r.entity_id)

        d = self.sendDeferred(p, timeout=DEFER_TIMEOUT)
        # add observer for joining the room
        self.xmlstream.addOnetimeObserver(PRESENCE+"[@from='%s' and @type='unavailable']" % (r.entity_id.full()), 
                                          self._leftRoom, 1, d)

        return d
    

    def status(self, room_jid, show=None, status=None):
        """Change user status.

        See: http://xmpp.org/extensions/xep-0045.html#changepres

        @param room_jid: The room jabber/xmpp entity id for the requested configuration form.
        @type  room_jid: L{jid.JID}

        @param show: The availability of the entity. Common values are xa, available, etc
        @type  show: L{unicode}

        @param show: The current status of the entity. 
        @type  show: L{unicode}

        """
        r = self._getRoom(room_jid)
        if r is None:
            raise NotFound

        p = BasicPresence(to=r.entityId()) 
        if status is not None:
            p.addElement('status', None, status)
            
        if show is not None:
            p.addElement('show', None, show)
            
        d = self.sendDeferred(p, timeout=DEFER_TIMEOUT)

        # add observer for joining the room
        self.xmlstream.addOnetimeObserver(PRESENCE+"[@from='%s']" % (r.entity_id.full()), 
                                          self._changed, 1, d, room_jid)

        return d

    def _sendMessage(self, msg, children=None):

        if children:
            for c in children:
                msg.addChild(c)
        
        self.xmlstream.send(msg)

    def groupChat(self, to, message, children=None):
        """Send a groupchat message
        """
        msg = GroupChat(to, body=message)
        
        self._sendMessage(msg, children=children)

    def chat(self, to, message, children=None):
        msg = PrivateChat(to, body=message)

        self._sendMessage(msg, children=children)
        
    def invite(self, to, reason=None, full_jid=None):
        """
        """
        msg = InviteMessage(to, reason=reason, full_jid=full_jid)
        self._sendMessage(msg)


    def password(self, to, password):
        p = PasswordPresence(to, password)

        self.xmlstream.send(p)
    
    def register(self, to, fields=[]):
        iq = RegisterRequest(self.xmlstream, method='set', fields=fields)
        iq['to'] = to
        return iq.send()


    def _getAffiliationList(self, room_jid, affiliation):
        iq = AffiliationRequest(self.xmlstream,
                                method='get',
                                affiliation=affiliation, 
                                )
        iq['to'] = room_jid.full()
        return iq.send()        


    def _getRoleList(self, room_jid, role):
        iq = RoleRequest(self.xmlstream,
                                method='get',
                                role=role,
                                )
        iq['to'] = room_jid.full()
        return iq.send()        


    def self._setAffiliationList(self, affiliation, room_jid, iq):
        r = self._getRoom(room_jid)
        if r is not None:
            affiliation_list = []
            setattr(r, affiliation, [])
            
            for item in iq.query.elements():
                nick   = item.getAttribute('nick', None)
                entity = item.getAttribute('jid', None)
                u      = None
                if nick is None and entity is None:
                    raise Exception, 'bad attributes in item list'
                if nick is not None:
                    u = room.getUser(nick)
                if u is None:
                    u = User(nick, user_jid=jid.internJID(entity))
                    u.affiliation = 'member'
                    
                affiliation_list.append(u)

            setattr(r, affiliation, affiliation_list)
        return r

    def getMemberList(self, room_jid):
        """ Get a member list from a room.

        @param room_jid: The room jabber/xmpp entity id for the requested member list.
        @type  room_jid: L{jid.JID}

        """
        d = self._getAffiliationList(room_jid, 'member')
        d.addCallback(self._setAffiliationList, 'members', room_jid)
        return d

    def getAdminList(self, room_jid):
        """ Get an admin list from a room.

        @param room_jid: The room jabber/xmpp entity id for the requested member list.
        @type  room_jid: L{jid.JID}

        """
        d = self._getAffiliationList(room_jid, 'admin')
        d.addCallback(self._setAffiliationList, 'members', room_jid)
        return d

    def getBanList(self, room_jid):
        """ Get an outcast list from a room.

        @param room_jid: The room jabber/xmpp entity id for the requested member list.
        @type  room_jid: L{jid.JID}

        """
        d = self._getAffiliationList(room_jid, 'outcast')
        d.addCallback(self._setAffiliationList, 'members', room_jid)
        return d

    def getOwnerList(self, room_jid):
        """ Get an owner list from a room.

        @param room_jid: The room jabber/xmpp entity id for the requested member list.
        @type  room_jid: L{jid.JID}

        """
        d = self._getAffiliationList(room_jid, 'owner')
        d.addCallback(self._setAffiliationList, 'members', room_jid)
        return d

    def getRegisterForm(self, room):
        """

        @param room: The room jabber/xmpp entity id for the requested registration form.
        @type  room: L{jid.JID}

        """
        iq = RegisterRequest(self.xmlstream)
        iq['to'] = room.userhost()
        return iq.send()

    def destroy(self, room_jid, reason=None):
        """ Destroy a room. 
        
        @param room_jid: The room jabber/xmpp entity id.
        @type  room_jid: L{jid.JID}
        
        """
        def destroyed(iq):
            self._removeRoom(room_jid)
            return True

        iq = OwnerRequest(self.xmlstream, method='set')
        d  = iq.query.addElement('destroy')
        d['jid'] = room_jid.userhost()
        if reason is not None:
            d.addElement('reason', None, reason)

        return iq.send().addCallback(destroyed)

    def subject(self, to, subject):
        """
        """
        msg = GroupChat(to, subject=subject)
        self.xmlstream.send(msg)

    def voice(self, to):
        """
        """
        msg = MessageVoice(to=to)
        self.xmlstream.send(msg)



    def history(self, to, message_list):
        """
        """
        
        for m in message_list:
            m['type'] = 'groupchat'
            mto = m['to']
            frm = m.getAttribute('from', None)
            m['to'] = to

            d = m.addElement('delay', NS_DELAY)
            d['stamp'] = self._makeTimeStamp()
            d['from'] = mto 

            self.xmlstream.send(m)

    def _setAffiliation(self, frm, room_jid, affiliation, reason=None, a_jid=None):
        iq = AffiliationRequest(self.xmlstream,
                                method='set',
                                affiliation=affiliation,
                                a_jid=a_jid, 
                                reason=reason)
        iq['to'] = room_jid.userhost() # this is a room jid, only send to room
        iq['from'] = frm.full()
        return iq.send()

    def _setRole(self, frm, room_jid, a_jid=None, reason=None, role='none'):
        iq = RoleRequest(self.xmlstream,
                         method='set',
                         a_jid=a_jid,
                         role=role,
                         reason=reason)
        iq['to'] = room_jid.userhost() # this is a room jid, only send to room
        iq['from'] = frm.full()
        return iq.send()

    def _cbRequest(self, room_jid, iq):
        r = self._getRoom(room_jid)
        if r is None:
            raise NotFound

        return r

    def grantVoice(self, frm, room_jid, reason=None):
        return self._setRole(frm, room_jid, role='participant', reason=reason)

    def grantVisitor(self, frm, room_jid, reason=None):
        return self._setRole(frm, room_jid, role='visitor', reason=reason)

    def grantModerator(self, frm, room_jid, reason=None):
        return self._setRole(frm, room_jid, role='moderator', reason=reason)

    def ban(self, to, ban_jid, frm, reason=None):
        return self._setAffiliation(frm, to, 'outcast', a_jid=ban_jid, reason=reason)

    def kick(self, to, kick_jid, frm, reason=None):        
        return self._setAffiliation(frm, to, 'none', a_jid=kick_jid, reason=reason)
        
