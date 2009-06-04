# -*- test-case-name: wokkel.test.test_compat -*-
#
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import protocol
from twisted.words.protocols.jabber import xmlstream
from twisted.words.xish import domish

class BootstrapMixin(object):
    """
    XmlStream factory mixin to install bootstrap event observers.

    This mixin is for factories providing
    L{IProtocolFactory<twisted.internet.interfaces.IProtocolFactory>} to make
    sure bootstrap event observers are set up on protocols, before incoming
    data is processed. Such protocols typically derive from
    L{utility.EventDispatcher}, like L{XmlStream}.

    You can set up bootstrap event observers using C{addBootstrap}. The
    C{event} and C{fn} parameters correspond with the C{event} and
    C{observerfn} arguments to L{utility.EventDispatcher.addObserver}.

    @since: 8.2.
    @ivar bootstraps: The list of registered bootstrap event observers.
    @type bootstrap: C{list}
    """

    def __init__(self):
        self.bootstraps = []


    def installBootstraps(self, dispatcher):
        """
        Install registered bootstrap observers.

        @param dispatcher: Event dispatcher to add the observers to.
        @type dispatcher: L{utility.EventDispatcher}
        """
        for event, fn in self.bootstraps:
            dispatcher.addObserver(event, fn)


    def addBootstrap(self, event, fn):
        """
        Add a bootstrap event handler.

        @param event: The event to register an observer for.
        @type event: C{str} or L{xpath.XPathQuery}
        @param fn: The observer callable to be registered.
        """
        self.bootstraps.append((event, fn))


    def removeBootstrap(self, event, fn):
        """
        Remove a bootstrap event handler.

        @param event: The event the observer is registered for.
        @type event: C{str} or L{xpath.XPathQuery}
        @param fn: The registered observer callable.
        """
        self.bootstraps.remove((event, fn))



class XmlStreamServerFactory(BootstrapMixin,
                             protocol.ServerFactory):
    """
    Factory for Jabber XmlStream objects as a server.

    @since: 8.2.
    @ivar authenticatorFactory: Factory callable that takes no arguments, to
                                create a fresh authenticator to be associated
                                with the XmlStream.
    """

    protocol = xmlstream.XmlStream

    def __init__(self, authenticatorFactory):
        BootstrapMixin.__init__(self)
        self.authenticatorFactory = authenticatorFactory


    def buildProtocol(self, addr):
        """
        Create an instance of XmlStream.

        A new authenticator instance will be created and passed to the new
        XmlStream. Registered bootstrap event observers are installed as well.
        """
        authenticator = self.authenticatorFactory()
        xs = self.protocol(authenticator)
        xs.factory = self
        self.installBootstraps(xs)
        return xs
