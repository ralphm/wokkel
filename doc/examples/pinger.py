"""
An XMPP subprotocol handler that acts as an XMPP Ping pinger.
"""

from wokkel.ping import PingClientProtocol

class Pinger(PingClientProtocol):
    """
    I send a ping as soon as I have a connection.
    """

    def __init__(self, entity, sender=None):
        self.entity = entity
        self.sender = sender

    def connectionInitialized(self):
        def cb(response):
            print "*** Pong ***"

        print "*** Ping ***"
        d = self.ping(self.entity, sender=self.sender)
        d.addCallback(cb)
