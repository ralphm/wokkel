# -*- coding: utf-8 -*-
# -*- test-case-name: wokkel.test.test_mam -*-
#
# Copyright (c) Adrien Cossa, Jérôme Poisson
# See LICENSE for details.

"""
XMPP Message Archive Management protocol.

This protocol is specified in
U{XEP-0313<http://xmpp.org/extensions/xep-0313.html>}.
"""

from dateutil import tz

from zope.interface import implements
from zope.interface import Interface

from twisted.words.protocols.jabber import xmlstream
from twisted.words.xish import domish
from twisted.words.protocols.jabber import jid
from twisted.words.protocols.jabber import error
from twisted.internet import defer
from twisted.python import log

from wokkel import subprotocols
from wokkel import disco
from wokkel import data_form
from wokkel import delay

import rsm

NS_MAM = 'urn:xmpp:mam:1'
NS_FORWARD = 'urn:xmpp:forward:0'

FIELDS_REQUEST = "/iq[@type='get']/query[@xmlns='%s']" % NS_MAM
ARCHIVE_REQUEST = "/iq[@type='set']/query[@xmlns='%s']" % NS_MAM
PREFS_GET_REQUEST = "/iq[@type='get']/prefs[@xmlns='%s']" % NS_MAM
PREFS_SET_REQUEST = "/iq[@type='set']/prefs[@xmlns='%s']" % NS_MAM

# TODO: add the tests!


class MAMError(error.StanzaError):
    """
    MAM error.
    """
    def __init__(self, text=None):
        error.StanzaError.__init__(self, 'bad-request', text=text)


class Unsupported(MAMError):
    def __init__(self, feature, text=None):
        self.feature = feature
        MAMError.__init__(self, 'feature-not-implemented',
                                'unsupported',
                                feature,
                                text)

    def __str__(self):
        message = MAMError.__str__(self)
        message += ', feature %r' % self.feature
        return message


class MAMRequest(object):
    """
    A Message Archive Management <query/> request.

    @ivar form: Data Form specifing the filters.
    @itype form: L{data_form.Form}

    @ivar rsm: RSM request instance.
    @itype rsm: L{rsm.RSMRequest}

    @ivar node: pubsub node id if querying a pubsub node, else None.
    @itype node: C{unicode}

    @ivar query_id: id to use to track the query
    @itype query_id: C{unicode}
    """
    # FIXME: should be based on generic.Stanza

    def __init__(self, form=None, rsm_=None, node=None, query_id=None, sender=None, recipient=None):
        if form is not None:
            assert form.formType == 'submit'
            assert form.formNamespace == NS_MAM
        self.form = form
        self.rsm = rsm_
        self.node = node
        self.query_id = query_id
        self.sender = sender
        self.recipient = recipient

    @classmethod
    def fromElement(cls, iq):
        """Parse the DOM representation of a MAM <query/> request.

        @param iq: <iq/> element containing a MAM <query/>.
        @type iq: L{Element<twisted.words.xish.domish.Element>}

        @return: MAMRequest instance.
        @rtype: L{MAMRequest}
        """
        sender = jid.JID(iq.getAttribute('from'))
        recipient = jid.JID(iq.getAttribute('to'))
        try:
            query = iq.elements(NS_MAM, 'query').next()
        except StopIteration:
            raise MAMError("Can't find MAM <query/> in element")
        form = data_form.findForm(query, NS_MAM)
        try:
            rsm_request = rsm.RSMRequest.fromElement(query)
        except rsm.RSMNotFoundError:
            rsm_request = None
        node = query.getAttribute('node')
        query_id = query.getAttribute('queryid')
        return MAMRequest(form, rsm_request, node, query_id, sender, recipient)

    def toElement(self):
        """
        Return the DOM representation of this RSM <query/> request.

        @rtype: L{Element<twisted.words.xish.domish.Element>}
        """
        mam_elt = domish.Element((NS_MAM, 'query'))
        if self.node is not None:
            mam_elt['node'] = self.node
        if self.query_id is not None:
            mam_elt['queryid'] = self.query_id
        if self.form is not None:
            mam_elt.addChild(self.form.toElement())
        if self.rsm is not None:
            mam_elt.addChild(self.rsm.toElement())

        return mam_elt

    def render(self, parent):
        """Embed the DOM representation of this MAM request in the given element.

        @param parent: parent IQ element.
        @type parent: L{Element<twisted.words.xish.domish.Element>}

        @return: MAM request element.
        @rtype: L{Element<twisted.words.xish.domish.Element>}
        """
        assert parent.name == 'iq'
        mam_elt = self.toElement()
        parent.addChild(mam_elt)
        return mam_elt


class MAMPrefs(object):
    """
    A Message Archive Management <prefs/> request.

    @param default: A value in ('always', 'never', 'roster').
    @type : C{unicode} or C{None}

    @param always (list): A list of JID instances.
    @type always: C{list}

    @param never (list): A list of JID instances.
    @type never: C{list}
    """

    def __init__(self, default=None, always=None, never=None):
        if default is not None:
            # default must be defined in response, but can be empty in request (see http://xmpp.org/extensions/xep-0313.html#config)
            assert default in ('always', 'never', 'roster')
        self.default = default
        if always is not None:
            assert isinstance(always, list)
        else:
            always = []
        self.always = always
        if never is not None:
            assert isinstance(never, list)
        else:
            never = []
        self.never = never

    @classmethod
    def fromElement(cls, prefs_elt):
        """Parse the DOM representation of a MAM <prefs/> request.

        @param prefs_elt: MAM <prefs/> request element.
        @type prefs_elt: L{Element<twisted.words.xish.domish.Element>}

        @return: MAMPrefs instance.
        @rtype: L{MAMPrefs}
        """
        if prefs_elt.uri != NS_MAM or prefs_elt.name != 'prefs':
            raise MAMError('Element provided is not a MAM <prefs/> request')
        try:
            default = prefs_elt['default']
        except KeyError:
            # FIXME: return proper error here
            raise MAMError('Element provided is not a valid MAM <prefs/> request')

        prefs = {}
        for attr in ('always', 'never'):
            prefs[attr] = []
            try:
                pref = prefs_elt.elements(NS_MAM, attr).next()
            except StopIteration:
                # FIXME: return proper error here
                raise MAMError('Element provided is not a valid MAM <prefs/> request')
            else:
                for jid_s in pref.elements(NS_MAM, 'jid'):
                    prefs[attr].append(jid.JID(jid_s))
        return MAMPrefs(default, **prefs)

    def toElement(self):
        """
        Return the DOM representation of this RSM <prefs/>request.

        @rtype: L{Element<twisted.words.xish.domish.Element>}
        """
        mam_elt = domish.Element((NS_MAM, 'prefs'))
        if self.default:
            mam_elt['default'] = self.default
        for attr in ('always', 'never'):
            attr_elt = mam_elt.addElement(attr)
            jids = getattr(self, attr)
            for jid_ in jids:
                attr_elt.addElement('jid', content=jid_.full())
        return mam_elt

    def render(self, parent):
        """Embed the DOM representation of this MAM request in the given element.

        @param parent: parent IQ element.
        @type parent: L{Element<twisted.words.xish.domish.Element>}

        @return: MAM request element.
        @rtype: L{Element<twisted.words.xish.domish.Element>}
        """
        assert parent.name == 'iq'
        mam_elt = self.toElement()
        parent.addChild(mam_elt)
        return mam_elt


class MAMClient(subprotocols.XMPPHandler):
    """
    MAM client.

    This handler implements the protocol for sending out MAM requests.
    """

    def queryArchive(self, mam_query, service=None, sender=None):
        """Query a user, MUC or pubsub archive.

        @param mam_query: query to use
        @type form: L{MAMRequest}

        @param service: Entity offering the MAM service (None for user server).
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param sender: Optional sender address.
        @type sender: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @return: A deferred that fires upon receiving a response.
        @rtype: L{Deferred<twisted.internet.defer.Deferred>}
        """
        iq = xmlstream.IQ(self.xmlstream, 'set')
        mam_query.render(iq)
        if sender is not None:
            iq['from'] = unicode(sender)
        return iq.send(to=service.full() if service else None)

    def queryFields(self, service=None, sender=None):
        """Ask the server about supported fields.

        @param service: Entity offering the MAM service (None for user archives).
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param sender: Optional sender address.
        @type sender: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @return: data Form with the fields, or None if not found
        @rtype: L{Deferred<twisted.internet.defer.Deferred>}
        """
        # http://xmpp.org/extensions/xep-0313.html#query-form
        iq = xmlstream.IQ(self.xmlstream, 'get')
        MAMRequest().render(iq)
        if sender is not None:
            iq['from'] = unicode(sender)
        d = iq.send(to=service.full() if service else None)
        d.addCallback(lambda iq_result: iq_result.elements(NS_MAM, 'query').next())
        d.addCallback(data_form.findForm, NS_MAM)
        return d

    def queryPrefs(self, service=None, sender=None):
        """Retrieve the current user preferences.

        @param service: Entity offering the MAM service (None for user archives).
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param sender: Optional sender address.
        @type sender: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @return: A deferred that fires upon receiving a response.
        @rtype: L{Deferred<twisted.internet.defer.Deferred>}
        """
        # http://xmpp.org/extensions/xep-0313.html#prefs
        iq = xmlstream.IQ(self.xmlstream, 'get')
        MAMPrefs().render(iq)
        if sender is not None:
            iq['from'] = unicode(sender)
        return iq.send(to=service.full() if service else None)

    def setPrefs(self, service=None, default='roster', always=None, never=None, sender=None):
        """Set new user preferences.

        @param service: Entity offering the MAM service (None for user archives).
        @type service: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @param default: A value in ('always', 'never', 'roster').
        @type : C{unicode}

        @param always (list): A list of JID instances.
        @type always: C{list}

        @param never (list): A list of JID instances.
        @type never: C{list}

        @param sender: Optional sender address.
        @type sender: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @return: A deferred that fires upon receiving a response.
        @rtype: L{Deferred<twisted.internet.defer.Deferred>}
        """
        # http://xmpp.org/extensions/xep-0313.html#prefs
        assert default is not None
        iq = xmlstream.IQ(self.xmlstream, 'set')
        MAMPrefs(default, always, never).render(iq)
        if sender is not None:
            iq['from'] = unicode(sender)
        return iq.send(to=service.full() if service else None)


class IMAMResource(Interface):

    def onArchiveRequest(self, mam):
        """

        @param mam: The MAM <query/> request.
        @type mam: L{MAMQueryReques<wokkel.mam.MAMRequest>}

        @return: The RSM answer.
        @rtype: L{RSMResponse<wokkel.rsm.RSMResponse>}
        """

    def onPrefsGetRequest(self, requestor):
        """

        @param requestor: JID of the requestor.
        @type requestor: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @return: The current settings.
        @rtype: L{wokkel.mam.MAMPrefs}
        """

    def onPrefsSetRequest(self, prefs, requestor):
        """

        @param prefs: The new settings to set.
        @type prefs: L{wokkel.mam.MAMPrefs}

        @param requestor: JID of the requestor.
        @type requestor: L{JID<twisted.words.protocols.jabber.jid.JID>}

        @return: The new current settings.
        @rtype: L{wokkel.mam.MAMPrefs}
        """

class IMAMService(Interface):
    """
    Interface for XMPP MAM service.
    """

    def addFilter(self, field):
        """
        Add a new filter for querying MAM archive.

        @param field: data form field of the filter
        @type field: L{Form<wokkel.data_form.Field>}
        """


class MAMService(subprotocols.XMPPHandler, subprotocols.IQHandlerMixin):
    """
    Protocol implementation for a MAM service.

    This handler waits for XMPP Ping requests and sends a response.
    """
    implements(IMAMService, disco.IDisco)

    _request_class = MAMRequest

    iqHandlers = {FIELDS_REQUEST: '_onFieldsRequest',
                  ARCHIVE_REQUEST: '_onArchiveRequest',
                  PREFS_GET_REQUEST: '_onPrefsGetRequest',
                  PREFS_SET_REQUEST: '_onPrefsSetRequest'
                  }

    _legacyFilters = {'start': {'fieldType': 'text-single',
                                'var': 'start',
                                'label': 'Starting time',
                                'desc': 'Starting time a the result period.',
                                },
                      'end': {'fieldType': 'text-single',
                              'var': 'end',
                              'label': 'Ending time',
                              'desc': 'Ending time of the result period.',
                              },
                      'with': {'fieldType': 'jid-single',
                               'var': 'with',
                               'label': 'Entity',
                               'desc': 'Entity against which to match message.',
                               },
                      }

    def __init__(self, resource):
        """
        @param resource: instance implementing IMAMResource
        @type resource: L{object}
        """
        self.resource = resource
        self.extra_fields = {}

    def connectionInitialized(self):
        """
        Called when the XML stream has been initialized.

        This sets up an observer for incoming ping requests.
        """
        self.xmlstream.addObserver(FIELDS_REQUEST, self.handleRequest)
        self.xmlstream.addObserver(ARCHIVE_REQUEST, self.handleRequest)
        self.xmlstream.addObserver(PREFS_GET_REQUEST, self.handleRequest)
        self.xmlstream.addObserver(PREFS_SET_REQUEST, self.handleRequest)

    def addFilter(self, field):
        """
        Add a new filter for querying MAM archive.

        @param field: data form field of the filter
        @type field: L{Form<wokkel.data_form.Field>}
        """
        self.extra_fields[field.var] = field

    def _onFieldsRequest(self, iq):
        """
        Called when a fields request has been received.

        This immediately replies with a result response.
        """
        iq.handled = True
        query = domish.Element((NS_MAM, 'query'))
        query.addChild(buildForm(extra_fields=self.extra_fields).toElement(), formType='form')
        return query

    def _onArchiveRequest(self, iq):
        """
        Called when a message archive request has been received.

        This replies with the list of archived message and the <iq> result
        @return: A tuple with list of message data (id, element, data) and RSM element
        @rtype: C{tuple}
        """
        iq.handled = True
        mam_ = self._request_class.fromElement(iq)

        # remove unsupported filters
        unsupported_fields = []
        if mam_.form:
            for key, field in mam_.form.fields.iteritems():
                if key not in self._legacyFilters and key not in self.extra_fields:
                    log.msg('Ignored unsupported MAM filter: %s' % field)
                    unsupported_fields.append(key)
        for key in unsupported_fields:
            del mam_.form.fields[key]

        def forwardMessage(id_, elt, date):
            msg = domish.Element((None, 'message'))
            msg['to'] = iq['from']
            result = msg.addElement((NS_MAM, 'result'))
            if mam_.query_id is not None:
                result['queryid'] = mam_.query_id
            result['id'] = id_
            forward = result.addElement((NS_FORWARD, 'forwarded'))
            forward.addChild(delay.Delay(date).toElement())
            forward.addChild(elt)
            self.xmlstream.send(msg)

        def cb(result):
            msg_data, rsm_elt = result
            for data in msg_data:
                forwardMessage(*data)

            fin_elt = domish.Element((NS_MAM, 'fin'))

            if rsm_elt is not None:
                fin_elt.addChild(rsm_elt)
            return fin_elt

        d = defer.maybeDeferred(self.resource.onArchiveRequest, mam_)
        d.addCallback(cb)
        return d

    def _onPrefsGetRequest(self, iq):
        """
        Called when a prefs get request has been received.

        This immediately replies with a result response.
        """
        iq.handled = True
        requestor = jid.JID(iq['from'])

        def cb(prefs):
            return prefs.toElement()

        d = self.resource.onPrefsGetRequest(requestor).addCallback(cb)
        return d

    def _onPrefsSetRequest(self, iq):
        """
        Called when a prefs get request has been received.

        This immediately replies with a result response.
        """
        iq.handled = True

        prefs = MAMPrefs.fromElement(iq.prefs)
        requestor = jid.JID(iq['from'])

        def cb(prefs):
            return prefs.toElement()

        d = self.resource.onPrefsSetRequest(prefs, requestor).addCallback(cb)
        return d

    def getDiscoInfo(self, requestor, target, nodeIdentifier=''):
        if nodeIdentifier:
            return []
        return [disco.DiscoFeature(NS_MAM)]

    def getDiscoItems(self, requestor, target, nodeIdentifier=''):
        return []


def datetime2utc(datetime_obj):
    """Convert a datetime to a XEP-0082 compliant UTC datetime.

    @param datetime_obj: Offset-aware timestamp to convert.
    @type datetime_obj: L{datetime<datetime.datetime>}

    @return: The datetime converted to UTC.
    @rtype: C{unicode}
    """
    stampFormat = '%Y-%m-%dT%H:%M:%SZ'
    return datetime_obj.astimezone(tz.tzutc()).strftime(stampFormat)


def buildForm(start=None, end=None, with_jid=None, extra_fields=None, formType='submit'):
    """Prepare a Data Form for MAM.

    @param start: Offset-aware timestamp to filter out older messages.
    @type start: L{datetime<datetime.datetime>}

    @param end: Offset-aware timestamp to filter out later messages.
    @type end: L{datetime<datetime.datetime>}

    @param with_jid: JID against which to match messages.
    @type with_jid: L{JID<twisted.words.protocols.jabber.jid.JID>}

    @param extra_fields: list of extra data form fields that are not defined by the
        specification.
    @type: C{list}

    @param formType: The type of the Data Form ('submit' or 'form').
    @type formType: C{unicode}

    @return: XEP-0004 Data Form object.
    @rtype: L{Form<wokkel.data_form.Form>}
    """
    form = data_form.Form(formType, formNamespace=NS_MAM)

    if formType == 'form':
        for kwargs in MAMService._legacyFilters.values():
            form.addField(data_form.Field(**kwargs))
    elif formType == 'submit':
        if start:
            form.addField(data_form.Field(var='start', value=datetime2utc(start)))
        if end:
            form.addField(data_form.Field(var='end', value=datetime2utc(end)))
        if with_jid:
            form.addField(data_form.Field(fieldType='jid-single', var='with', value=with_jid.full()))

    if extra_fields is not None:
        for field in extra_fields:
            form.addField(field)

    return form
