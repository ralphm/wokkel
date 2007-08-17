# Copyright (c) 2003-2007 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.pubsub}
"""

from twisted.trial import unittest
from twisted.words.xish import domish
from twisted.words.protocols.jabber import error
from twisted.words.protocols.jabber.jid import JID

from wokkel import pubsub

class PubSubServiceTest(unittest.TestCase):

    def setUp(self):
        self.output = []

    def send(self, obj):
        self.output.append(obj)

    def test_onPublishNoNode(self):
        handler = pubsub.PubSubService()
        handler.manager = self
        iq = domish.Element((None, 'iq'))
        iq['from'] = 'user@example.org'
        iq['type'] = 'set'
        iq.addElement(('http://jabber.org/protocol/pubsub', 'pubsub'))
        iq.pubsub.addElement('publish')
        handler.handleRequest(iq)

        e = error.exceptionFromStanza(self.output[-1])
        self.assertEquals('bad-request', e.condition)

    def test_onPublish(self):
        class Handler(pubsub.PubSubService):
            def publish(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        handler = Handler()
        handler.manager = self
        iq = domish.Element((None, 'iq'))
        iq['type'] = 'set'
        iq['from'] = 'user@example.org'
        iq.addElement(('http://jabber.org/protocol/pubsub', 'pubsub'))
        iq.pubsub.addElement('publish')
        iq.pubsub.publish['node'] = 'test'
        handler.handleRequest(iq)

        self.assertEqual((JID('user@example.org'), 'test', []), handler.args)

    def test_onOptionsGet(self):
        handler = pubsub.PubSubService()
        handler.manager = self
        iq = domish.Element((None, 'iq'))
        iq['from'] = 'user@example.org'
        iq['type'] = 'get'
        iq.addElement(('http://jabber.org/protocol/pubsub', 'pubsub'))
        iq.pubsub.addElement('options')
        handler.handleRequest(iq)

        e = error.exceptionFromStanza(self.output[-1])
        self.assertEquals('feature-not-implemented', e.condition)
        self.assertEquals('unsupported', e.appCondition.name)
        self.assertEquals('http://jabber.org/protocol/pubsub#errors',
                          e.appCondition.uri)
