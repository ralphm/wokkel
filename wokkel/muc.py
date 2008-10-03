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

from twisted.internet import defer
from twisted.words.protocols.jabber import jid, error, xmlstream
from twisted.words.xish import domish

from wokkel import disco, data_form, shim, xmppim
from wokkel.subprotocols import IQHandlerMixin, XMPPHandler
from wokkel.iwokkel import IMUCClient

# Multi User Chat namespaces
NS          = 'http://jabber.org/protocol/muc'
NS_USER     = NS + '#user'
NS_ADMIN    = NS + '#admin'
NS_OWNER    = NS + '#owner'
NS_ROOMINFO = NS + '#roominfo'
NS_CONFIG   = NS + '#roomconfig'
NS_REQUEST  = NS + '#request'
NS_REGISTER = NS + '#register'

NS_DELAY    = 'urn:xmpp:delay'
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

MUC_ADMIN = IQ_QUERY+'[@xmlns="' + NS_ADMIN + '"]'
MUC_OWNER = IQ_QUERY+'[@xmlns="' + NS_OWNER + '"]'

MUC_AO = MUC_ADMIN + '|' + MUC_OWNER


MESSAGE  = '/message'
PRESENCE = '/presence'

CHAT_BODY = MESSAGE +'[@type="chat"]/body'
CHAT      = MESSAGE +'[@type="chat"]'

GROUPCHAT     = MESSAGE +'[@type="groupchat"]/body'
SUBJECT       = MESSAGE +'[@type="groupchat"]/body'
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


class MUCError(error.StanzaError):
    """
    Exception with muc specific condition.
    """
    def __init__(self, condition, mucCondition, feature=None, text=None):
        appCondition = domish.Element((NS, mucCondition))
        if feature:
            appCondition['feature'] = feature
        error.StanzaError.__init__(self, condition,
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

    @ivar namespace: Request namespace.
    @type namespace: C{str}
    @ivar method: Type attribute of the IQ request. Either C{'set'} or C{'get'}
    @type method: C{str}
    """

    def __init__(self, xs, method='get', fields=[]):
        xmlstream.IQ.__init__(self, xs, method)
        q = self.addElement((NS_OWNER, 'query'))
        if method == 'set':
            # build data form
            form = data_form.Form('submit', formNamespace=NS_CONFIG)
            q.addChild(form.toElement())
            
            for f in fields:
                # create a field
                form.addField(f)


class RegisterRequest(xmlstream.IQ):
    """
    Register room request.

    @ivar namespace: Request namespace.
    @type namespace: C{str}
    @ivar method: Type attribute of the IQ request. Either C{'set'} or C{'get'}
    @type method: C{str}
    """

    def __init__(self, xs, method='get', fields=[]):
        xmlstream.IQ.__init__(self, xs, method)
        q = self.addElement((NS_REQUEST, 'query'))
        if method == 'set':
            # build data form
            form_type = 'submit'        
            form = data_form.Form(form_type, formNamespace=NS_REGISTER)
            q.addChild(form.toElement())        
            
            for f in fields:
                # create a field
                form.addField(f)

class GroupChat(domish.Element):
    """
    """
    def __init__(self, to, body=None, subject=None, frm=None):
        """To needs to be a string
        """
        domish.Element.__init__(self, (None, 'message'))
        self['type'] = 'groupchat'
        self['to']   = to 
        if frm:
            self['from'] = frm
        if body:
            self.addElement('body',None, body)
        if subject:
            self.addElement('subject',None, subject)
            


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
        self.status = None

        self.entity_id = jid.internJID(name+'@'+server+'/'+nick)
               
        self.roster = {}

        

class BasicPresence(xmppim.AvailablePresence):
    """
    This behaves like an object providing L{domish.IElement}.

    """

    def __init__(self, to=None, show=None, statuses=None):
        xmppim.AvailablePresence.__init__(self, to=to, show=show, statuses=statuses)
        # add muc elements
        x = self.addElement('x', NS)


class UserPresence(xmppim.Presence):
    """
    This behaves like an object providing L{domish.IElement}.

    """

    def __init__(self, to=None, type=None, frm=None, affiliation=None, role=None):
        xmppim.Presence.__init__(self, to, type)
        if frm:
            self['from'] = frm
        # add muc elements
        x = self.addElement('x', NS_USER)
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
        form = data_form.Form('submit', formNamespace=NS_REQUEST)
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
        x = self.addElement('x', NS)
        # add error 
        self.addChild(error)
        

class MUCClient(XMPPHandler):
    """
    Multi-User chat client protocol.
    """

    implements(IMUCClient)

    rooms = {}

    def connectionInitialized(self):
        self.xmlstream.addObserver(PRESENCE+"/x", self._onXPresence)
        self.xmlstream.addObserver(GROUPCHAT, self._onGroupChat)
        self.xmlstream.addObserver(SUBJECT, self._onSubject)
        # add history

    def _setRoom(self, room):
        self.rooms[room.entity_id.full().lower()] = room

    def _getRoom(self, room_jid):
        return self.rooms.get(room_jid.full().lower())

    def _removeRoom(self, room_jid):
        if self.rooms.has_key(room_jid.full().lower()):
            del self.rooms[room_jid.full().lower()]

    def _onXPresence(self, prs):
        """
        """
        if prs.x.uri == NS_USER:
            self.receivedUserPresence(prs)
            

    def _onGroupChat(self, msg):
        """
        """
        self.receivedGroupChat(msg)



    def _onSubject(self, msg):
        """
        """
        self.receivedSubject(msg)


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
            d.errback(prs)
        else:    
            # change the state of the room
            r = self._getRoom(room_jid)
            if r is None:
                raise Exception, 'Room Not Found' 
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
            d.errback(prs)
        else:    
            # change the state of the room
            r = self._getRoom(room_jid)
            if r is None:
                raise Exception, 'Room Not Found' 
            self._removeRoom(room_jid)
            
            d.callback(True)

    def receivedUserPresence(self, prs):
        """User Presence has been received
        """
        pass
        

    def receivedSubject(self, msg):
        """
        """
        pass

    def _cbDisco(self, iq):
        # grab query
        
        return getattr(iq,'query', None)
        
    def disco(self, entity, type='info'):
        """Send disco queries to a XMPP entity
        """

        iq = disco.DiscoRequest(self.xmlstream, disco.NS_INFO, 'get')
        iq['to'] = entity

        return iq.send().addBoth(self._cbDisco)
        

    def configure(self, room_jid, fields=[]):
        """Configure a room
        """
        request = ConfigureRequest(self.xmlstream, method='set', fields=fields)
        request['to'] = room_jid
        
        return request.send()

    def getConfigureForm(self, room_jid):
        request = ConfigureRequest(self.xmlstream)
        request['to'] = room_jid
        return request.send()


    def join(self, server, room, nick):
        """
        """
        d = defer.Deferred()
        r = Room(room, server, nick, state='joining')
        self._setRoom(r)
 
        p = BasicPresence(to=r.entity_id)
        # p['from'] = self.jid.full()
        self.xmlstream.send(p)

        # add observer for joining the room
        self.xmlstream.addOnetimeObserver(PRESENCE+"[@from='%s']" % (r.entity_id.full()), 
                                          self._joinedRoom, 1, d)

        return d
    

    
    def leave(self, room_jid):
        """
        """
        d = defer.Deferred()

        self._getRoom(room_jid)
 
        p = xmppim.UnavailablePresence(to=r.entity_id)
        # p['from'] = self.jid.full()
        self.xmlstream.send(p)

        # add observer for joining the room
        self.xmlstream.addOnetimeObserver(PRESENCE+"[@from='%s' and type='unavailable']" % (r.entity_id.full()), 
                                          self._leftRoom, 1, d)

        return d
    

    

    def groupChat(self, to, message, children=None):
        """Send a groupchat message
        """
        msg = GroupChat(to, body=message)

        if children:
            for c in children:
                msg.addChild(c)
        
        self.xmlstream.send(msg)

    
    def register(self, to, fields=[]):
        iq = RegisterRequest(self.xmlstream, method='set', fields=fields)
        iq['to'] = to
        return iq.send()

    def getRegisterForm(self, to):
        iq = RegisterRequest(self.xmlstream)
        iq['to'] = to
        return iq.send()

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

