# -*- test-case-name: wokkel.test.test_shim -*-
#
# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for {wokkel.shim}.
"""

from __future__ import division, absolute_import

from twisted.python.compat import unicode
from twisted.trial import unittest

from wokkel import shim
from wokkel.generic import parseXml

NS_SHIM = 'http://jabber.org/protocol/shim'

class HeadersTest(unittest.TestCase):
    """
    Tests for L{wokkel.shim.headers}.
    """

    def test_noHeaders(self):
        headers = shim.Headers([])
        self.assertEquals(NS_SHIM, headers.uri)
        self.assertEquals('headers', headers.name)
        self.assertEquals([], headers.children)

    def test_header(self):
        headers = shim.Headers([('Urgency', 'high')])
        elements = list(headers.elements())
        self.assertEquals(1, len(elements))
        header = elements[0]
        self.assertEquals(NS_SHIM, header.uri)
        self.assertEquals('header', header.name)
        self.assertEquals('Urgency', header['name'])
        self.assertEquals('high', unicode(header))


    def test_headerRepeated(self):
        """
        Some headers can appear more than once with the same name.
        """
        headers = shim.Headers([('Collection', 'node1'),
                           ('Collection', 'node2')])
        elements = list(headers.elements())
        self.assertEquals(2, len(elements))
        collections = set((unicode(element) for element in elements
                           if element['name'] == 'Collection'))
        self.assertIn('node1', collections)
        self.assertIn('node2', collections)



class ExtractHeadersTest(unittest.TestCase):
    """
    Tests for L{wokkel.shim.extractHeaders}.
    """

    def test_noHeaders(self):
        """
        A stanza without headers results in an empty dictionary.
        """
        stanza = parseXml("""<message/>""")
        headers = shim.extractHeaders(stanza)
        self.assertEquals({}, headers)

    def test_headers(self):
        """
        A stanza with headers results in a dictionary with those headers.
        """
        xml = """<message>
                   <headers xmlns='http://jabber.org/protocol/shim'>
                     <header name='Collection'>node1</header>
                     <header name='Urgency'>high</header>
                   </headers>
                 </message>"""

        stanza = parseXml(xml)
        headers = shim.extractHeaders(stanza)
        self.assertEquals({'Urgency': ['high'],
                           'Collection': ['node1']}, headers)


    def test_headersRepeated(self):
        """
        Some headers may appear repeatedly. Make sure all values are extracted.
        """
        xml = """<message>
                   <headers xmlns='http://jabber.org/protocol/shim'>
                     <header name='Collection'>node1</header>
                     <header name='Urgency'>high</header>
                     <header name='Collection'>node2</header>
                   </headers>
                 </message>"""

        stanza = parseXml(xml)
        headers = shim.extractHeaders(stanza)
        self.assertEquals({'Urgency': ['high'],
                           'Collection': ['node1', 'node2']}, headers)
