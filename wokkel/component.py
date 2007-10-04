# Copyright (c) 2003-2007 Ralph Meijer
# See LICENSE for details.

"""
XMPP External Component utilities
"""

from twisted.application import service
from twisted.internet import reactor
from twisted.words.protocols.jabber import component
from twisted.words.xish import domish

from wokkel.subprotocols import StreamManager

class Component(StreamManager, service.Service):
    def __init__(self, host, port, jid, password):
        self.host = host
        self.port = port

        factory = component.componentFactory(jid, password)

        StreamManager.__init__(self, factory)

    def _authd(self, xs):
        old_send = xs.send

        def send(obj):
            if domish.IElement.providedBy(obj) and \
                    not obj.getAttribute('from'):
                obj['from'] = self.xmlstream.thisEntity.full()
            old_send(obj)

        xs.send = send
        StreamManager._authd(self, xs)

    def initializationFailed(self, reason):
        """
        Called when stream initialization has failed.

        Stop the service (thereby disconnecting the current stream) and
        raise the exception.
        """
        self.stopService()
        reason.raiseException()

    def startService(self):
        service.Service.startService(self)

        self.factory.stopTrying()
        self._connection = self._getConnection()

    def stopService(self):
        service.Service.stopService(self)

        self._connection.disconnect()

    def _getConnection(self):
        return reactor.connectTCP(self.host, self.port, self.factory)
