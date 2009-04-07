# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# Copyright (c) 2008-2009 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.compat}.
"""

from zope.interface.verify import verifyObject
from twisted.internet import defer, protocol
from twisted.internet.interfaces import IProtocolFactory
from twisted.trial import unittest
from twisted.words.xish import domish, utility
from twisted.words.protocols.jabber import xmlstream
from wokkel.compat import BootstrapMixin, XmlStreamServerFactory

class DummyProtocol(protocol.Protocol, utility.EventDispatcher):
    """
    I am a protocol with an event dispatcher without further processing.

    This protocol is only used for testing BootstrapMixin to make
    sure the bootstrap observers are added to the protocol instance.
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.observers = []

        utility.EventDispatcher.__init__(self)



class BootstrapMixinTest(unittest.TestCase):
    """
    Tests for L{BootstrapMixin}.

    @ivar factory: Instance of the factory or mixin under test.
    """

    def setUp(self):
        self.factory = BootstrapMixin()


    def test_installBootstraps(self):
        """
        Dispatching an event should fire registered bootstrap observers.
        """
        called = []

        def cb(data):
            called.append(data)

        dispatcher = DummyProtocol()
        self.factory.addBootstrap('//event/myevent', cb)
        self.factory.installBootstraps(dispatcher)

        dispatcher.dispatch(None, '//event/myevent')
        self.assertEquals(1, len(called))


    def test_addAndRemoveBootstrap(self):
        """
        Test addition and removal of a bootstrap event handler.
        """

        called = []

        def cb(data):
            called.append(data)

        self.factory.addBootstrap('//event/myevent', cb)
        self.factory.removeBootstrap('//event/myevent', cb)

        dispatcher = DummyProtocol()
        self.factory.installBootstraps(dispatcher)

        dispatcher.dispatch(None, '//event/myevent')
        self.assertFalse(called)



class XmlStreamServerFactoryTest(BootstrapMixinTest):
    """
    Tests for L{XmlStreamServerFactory}.
    """

    def setUp(self):
        """
        Set up a server factory with a authenticator factory function.
        """
        class TestAuthenticator(object):
            def __init__(self):
                self.xmlstreams = []

            def associateWithStream(self, xs):
                self.xmlstreams.append(xs)

        def authenticatorFactory():
            return TestAuthenticator()

        self.factory = XmlStreamServerFactory(authenticatorFactory)


    def test_interface(self):
        """
        L{XmlStreamServerFactory} is a L{Factory}.
        """
        verifyObject(IProtocolFactory, self.factory)


    def test_buildProtocolAuthenticatorInstantiation(self):
        """
        The authenticator factory should be used to instantiate the
        authenticator and pass it to the protocol.

        The default protocol, L{XmlStream} stores the authenticator it is
        passed, and calls its C{associateWithStream} method. so we use that to
        check whether our authenticator factory is used and the protocol
        instance gets an authenticator.
        """
        xs = self.factory.buildProtocol(None)
        self.assertEquals([xs], xs.authenticator.xmlstreams)


    def test_buildProtocolXmlStream(self):
        """
        The protocol factory creates Jabber XML Stream protocols by default.
        """
        xs = self.factory.buildProtocol(None)
        self.assertIsInstance(xs, xmlstream.XmlStream)


    def test_buildProtocolTwice(self):
        """
        Subsequent calls to buildProtocol should result in different instances
        of the protocol, as well as their authenticators.
        """
        xs1 = self.factory.buildProtocol(None)
        xs2 = self.factory.buildProtocol(None)
        self.assertNotIdentical(xs1, xs2)
        self.assertNotIdentical(xs1.authenticator, xs2.authenticator)


    def test_buildProtocolInstallsBootstraps(self):
        """
        The protocol factory installs bootstrap event handlers on the protocol.
        """
        called = []

        def cb(data):
            called.append(data)

        self.factory.addBootstrap('//event/myevent', cb)

        xs = self.factory.buildProtocol(None)
        xs.dispatch(None, '//event/myevent')

        self.assertEquals(1, len(called))


    def test_buildProtocolStoresFactory(self):
        """
        The protocol factory is saved in the protocol.
        """
        xs = self.factory.buildProtocol(None)
        self.assertIdentical(self.factory, xs.factory)
