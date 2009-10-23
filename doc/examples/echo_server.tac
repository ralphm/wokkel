"""
An XMPP echo server as a standalone server via s2s.

This echo server accepts and initiates server-to-server connections using
dialback and listens on C{127.0.0.1} with the domain C{localhost}. It will
accept subscription requests for any potential entity at the domain and
send back messages sent to it.
"""

from twisted.application import service, strports
from twisted.words.protocols.jabber.xmlstream import toResponse
from wokkel import component, server, xmppim

# Configuration parameters

S2S_PORT = 'tcp:5269:interface=127.0.0.1'
SECRET = 'secret'
DOMAIN = 'localhost'
LOG_TRAFFIC = True


# Protocol handlers

class PresenceAcceptingHandler(xmppim.PresenceProtocol):
    """
    Presence accepting XMPP subprotocol handler.

    This handler blindly accepts incoming presence subscription requests,
    confirms unsubscription requests and responds to presence probes.

    Note that this handler does not remember any contacts, so it will not
    send presence when starting.
    """
    def subscribedReceived(self, presence):
        """
        Subscription approval confirmation was received.

        This is just a confirmation. Don't respond.
        """
        pass


    def unsubscribedReceived(self, presence):
        """
        Unsubscription confirmation was received.

        This is just a confirmation. Don't respond.
        """
        pass


    def subscribeReceived(self, presence):
        """
        Subscription request was received.

        Always grant permission to see our presence.
        """
        self.subscribed(recipient=presence.sender,
                        sender=presence.recipient)
        self.available(recipient=presence.sender,
                       status=u"I'm here",
                       sender=presence.recipient)


    def unsubscribeReceived(self, presence):
        """
        Unsubscription request was received.

        Always confirm unsubscription requests.
        """
        self.unsubscribed(recipient=presence.sender,
                          sender=presence.recipient)



    def probeReceived(self, presence):
        """
        A presence probe was received.

        Always send available presence to whoever is asking.
        """
        self.available(recipient=presence.sender,
                       status=u"I'm here",
                       sender=presence.recipient)



class EchoHandler(xmppim.MessageProtocol):
    """
    Message echoing XMPP subprotocol handler.
    """

    def onMessage(self, message):
        """
        Called when a message stanza was received.
        """

        # Ignore error messages
        if message.getAttribute('type') == 'error':
            return

        # Echo incoming messages, if they have a body.
        if message.body and unicode(message.body):
            response = toResponse(message, message.getAttribute('type'))
            response.addElement('body', content=unicode(message.body))
            self.send(response)



# Set up the Twisted application

application = service.Application("Ping Server")

router = component.Router()

serverService = server.ServerService(router, domain=DOMAIN, secret=SECRET)
serverService.logTraffic = LOG_TRAFFIC

s2sFactory = server.XMPPS2SServerFactory(serverService)
s2sFactory.logTraffic = LOG_TRAFFIC
s2sService = strports.service(S2S_PORT, s2sFactory)
s2sService.setServiceParent(application)

echoComponent = component.InternalComponent(router, DOMAIN)
echoComponent.logTraffic = LOG_TRAFFIC
echoComponent.setServiceParent(application)

presenceHandler = PresenceAcceptingHandler()
presenceHandler.setHandlerParent(echoComponent)

echoHandler = EchoHandler()
echoHandler.setHandlerParent(echoComponent)
