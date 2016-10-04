# Copyright (c) Ralph Meijer.
# See LICENSE for details.

"""
Tests for L{wokkel.format}
"""

from __future__ import division, absolute_import

from twisted.trial import unittest
from twisted.words.xish import domish

from wokkel import formats

class MoodTests(unittest.TestCase):
    """
    Tests for L{formats.Mood}.
    """

    def test_fromXml(self):
        """
        Moods are parsed from Elements.
        """
        element = domish.Element((formats.NS_MOOD, u'mood'))
        element.addElement(u'happy')
        element.addElement(u'text', content=u"Really happy!")
        mood = formats.Mood.fromXml(element)
        self.assertEquals(u'happy', mood.value)
        self.assertEquals(u'Really happy!', mood.text)



class TuneTests(unittest.TestCase):
    """
    Tests for L{formats.Tune}.
    """

    def test_fromXmlTrack(self):
        """
        The track filed in a user tune is parsed.
        """
        element = domish.Element((formats.NS_TUNE, u'tune'))
        element.addElement(u'track', content=u"The Power")
        tune = formats.Tune.fromXml(element)
        self.assertEquals(u'The Power', tune.track)


    def test_fromXmlLength(self):
        """
        The length filed in a user tune is parsed as an int.
        """
        element = domish.Element((formats.NS_TUNE, u'tune'))
        element.addElement(u'length', content=u"322")
        tune = formats.Tune.fromXml(element)
        self.assertEquals(322, tune.length)
