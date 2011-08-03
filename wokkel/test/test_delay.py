# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.delay}.
"""

from datetime import datetime
import dateutil.tz

from twisted.trial import unittest
from twisted.words.protocols.jabber.jid import JID

from wokkel.delay import Delay, DelayMixin
from wokkel.generic import Stanza, parseXml

class DelayTest(unittest.TestCase):
    """
    Tests for L{delay.Delay}.
    """

    def test_toElement(self):
        """
        The DOM structure has the serialized timestamp and sender address.
        """
        delay = Delay(stamp=datetime(2002, 9, 10, 23, 8, 25,
                                  tzinfo=dateutil.tz.tzutc()),
                      sender=JID(u'user@example.org'))
        element = delay.toElement()

        self.assertEqual(u'urn:xmpp:delay', element.uri)
        self.assertEqual(u'delay', element.name)
        self.assertEqual(u'2002-09-10T23:08:25Z', element.getAttribute('stamp'))
        self.assertEqual(u'user@example.org', element.getAttribute('from'))


    def test_toElementStampMissing(self):
        """
        To render to XML, at least a timestamp must be provided.
        """
        delay = Delay(stamp=None)
        self.assertRaises(ValueError, delay.toElement)


    def test_toElementStampOffsetNaive(self):
        """
        The provided timestamp must be offset aware.
        """
        delay = Delay(stamp=datetime(2002, 9, 10, 23, 8, 25))
        self.assertRaises(ValueError, delay.toElement)


    def test_toElementLegacy(self):
        """
        The legacy format uses C{CCYYMMDDThh:mm:ss} in the old namespace.
        """
        delay = Delay(stamp=datetime(2002, 9, 10, 23, 8, 25,
                                  tzinfo=dateutil.tz.tzutc()),
                      sender=JID(u'user@example.org'))
        element = delay.toElement(legacy=True)

        self.assertEqual(u'jabber:x:delay', element.uri)
        self.assertEqual(u'x', element.name)
        self.assertEqual(u'20020910T23:08:25', element.getAttribute('stamp'))
        self.assertEqual(u'user@example.org', element.getAttribute('from'))


    def test_fromElement(self):
        """
        The timestamp is parsed with the proper timezone (UTC).
        """
        xml = parseXml(u"""
            <delay xmlns="urn:xmpp:delay" stamp="2002-09-10T23:08:25Z"/>
        """)

        delay = Delay.fromElement(xml)
        self.assertEqual(datetime(2002, 9, 10, 23, 8, 25,
                                  tzinfo=dateutil.tz.tzutc()),
                         delay.stamp)
        self.assertIdentical(None, delay.sender)


    def test_fromElementLegacy(self):
        """
        For legacy XEP-0091 support, the timestamp is assumed to be in UTC.
        """
        xml = parseXml(u"""
            <x xmlns="jabber:x:delay" stamp="20020910T23:08:25"/>
        """)

        delay = Delay.fromElement(xml)
        self.assertEqual(datetime(2002, 9, 10, 23, 8, 25,
                                  tzinfo=dateutil.tz.tzutc()),
                         delay.stamp)
        self.assertIdentical(None, delay.sender)


    def test_fromElementSender(self):
        """
        The optional original sender address is parsed as a JID.
        """
        xml = parseXml(u"""
            <delay xmlns="urn:xmpp:delay" stamp="2002-09-10T23:08:25Z"
                                          from="user@example.org"/>
        """)

        delay = Delay.fromElement(xml)
        self.assertEqual(JID(u'user@example.org'), delay.sender)


    def test_fromElementSenderBad(self):
        """
        An invalid original sender address results in C{None}.
        """
        xml = parseXml(u"""
            <delay xmlns="urn:xmpp:delay" stamp="2002-09-10T23:08:25Z"
                                          from="user@@example.org"/>
        """)

        delay = Delay.fromElement(xml)
        self.assertIdentical(None, delay.sender)


    def test_fromElementMissingStamp(self):
        """
        A missing timestamp results in C{None} for the stamp attribute.
        """
        xml = parseXml(u"""
            <delay xmlns="urn:xmpp:delay"/>
        """)

        delay = Delay.fromElement(xml)
        self.assertIdentical(None, delay.stamp)


    def test_fromElementBadStamp(self):
        """
        A malformed timestamp results in C{None} for the stamp attribute.
        """
        xml = parseXml(u"""
            <delay xmlns="urn:xmpp:delay" stamp="foobar"/>
        """)

        delay = Delay.fromElement(xml)
        self.assertIdentical(None, delay.stamp)



class DelayStanza(Stanza, DelayMixin):
    """
    Test stanza class that mixes in delayed delivery information parsing.
    """



class DelayMixinTest(unittest.TestCase):

    def test_fromParentElement(self):
        """
        A child element with delay information is found and parsed.
        """
        xml = parseXml(u"""
            <message>
              <delay xmlns="urn:xmpp:delay" stamp="2002-09-10T23:08:25Z"/>
            </message>
        """)
        stanza = DelayStanza.fromElement(xml)
        self.assertNotIdentical(None, stanza.delay)


    def test_fromParentElementLegacy(self):
        """
        A child element with legacy delay information is found and parsed.
        """
        xml = parseXml(u"""
            <message>
              <x xmlns="jabber:x:delay" stamp="20020910T23:08:25"/>
            </message>
        """)
        stanza = DelayStanza.fromElement(xml)
        self.assertNotIdentical(None, stanza.delay)


    def test_fromParentElementBothLegacyLast(self):
        """
        The XEP-0203 format is used over later legacy XEP-0091 format.
        """
        xml = parseXml(u"""
            <message>
              <delay xmlns="urn:xmpp:delay" stamp="2002-09-10T23:08:25Z"/>
              <x xmlns="jabber:x:delay" stamp="20010910T23:08:25"/>
            </message>
        """)
        stanza = DelayStanza.fromElement(xml)
        self.assertNotIdentical(None, stanza.delay)
        self.assertEqual(2002, stanza.delay.stamp.year)


    def test_fromParentElementBothLegacyFirst(self):
        """
        The XEP-0203 format is used over earlier legacy XEP-0091 format.
        """
        xml = parseXml(u"""
            <message>
              <x xmlns="jabber:x:delay" stamp="20010910T23:08:25"/>
              <delay xmlns="urn:xmpp:delay" stamp="2002-09-10T23:08:25Z"/>
            </message>
        """)
        stanza = DelayStanza.fromElement(xml)
        self.assertNotIdentical(None, stanza.delay)
        self.assertEqual(2002, stanza.delay.stamp.year)
