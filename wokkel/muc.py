# -*- test-case-name: wokkel.test.test_muc -*-
#
# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
XMPP Multi-User Chat protocol.

This protocol is specified in
U{XEP-0045<http://www.xmpp.org/extensions/xep-0045.html>}.
"""

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

GROUPCHAT    = MESSAGE +'[@type="groupchat"]'
MESSAGE_ERROR = MESSAGE +'[@type="error"]'



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
        
        self.entity_id = jid.internJID(name+'@'+server+'/'+nick)
               
        self.roster = {}

        

class BasicPresence(xmppim.Presence):
    """
    This behaves like an object providing L{domish.IElement}.

    """

    def __init__(self, to=None, type=None):
        xmppim.Presence.__init__(self, to, type)
        
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


class PresenceError(BasicPresence):
    """
    This behaves like an object providing L{domish.IElement}.

    """

    def __init__(self, error, to=None, frm=None):
        BasicPresence.__init__(self, to, type='error')
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


    def connectionInitialized(self):
        self.rooms = {}
        

    def _setRoom(self, room):
        self.rooms[room.entity_id.full().lower()] = room

    def _getRoom(self, room_jid):
        return self.rooms.get(room_jid.full().lower())



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
            r.state = 'joined'
            d.callback(r)

    def userPresence(self, prs):
        """User Presence has been received
        """
        pass
        

    def _cbDisco(self, iq):
        # grab query
        
        return iq.query
        
    def disco(self, entity, type='info'):
        """Send disco queries to a XMPP entity
        """

        iq = disco.DiscoRequest(self.xmlstream, disco.NS_INFO, 'get')
        iq['to'] = entity

        return iq.send().addCallback(self._cbDisco)
        

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
    

