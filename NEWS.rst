News
====

Versions after 0.7.1 follow `CalVer <http://calver.org>`_ with a strict backwards compatibility policy.
The third digit is only for regressions.

Changes for the upcoming release can be found in the `wokkel/newsfragments` directory.

..
   Do *NOT* add changelog entries here!

	 This changelog is managed by towncrier and is compiled at release time from
   the news fragments directory.

.. towncrier release notes start

Wokkel 18.0.0 (2018-12-04)
==========================

Features
--------

- Wokkel has been ported to Python 3. (#81)
- wokkel.pubsub.PubSubClient now supports retrieving items by identifier. (#82)


Fixes
-----

- wokkel.generic.Request.stanzaType now defaults to the value of the class
  variable if `stanzaType` is not passed to `__init__`. (#80)
- wokkel.delay.Delay.fromElement now also catches `TypeError` when parsing
  timestamps, to work around a bug in dateutil. (#83)
- wokkel.muc.MUCClientProtocol now properly updates user role and affiliation
  upon presence updates. (#84)


Deprecations and Removals
-------------------------

- wokkel.generic.prepareIDNName is deprecated in favor of
  unicode.encode('idna'). (#85)
- Python 2.6 and older are no longer supported. (#86)
- wokkel.compat no longer includes named and value constants (now in
  `twisted.python.constants` through `constantly`). (#87)
- wokkel.compat no longer includes `BootstrapMixin` and
  `XmlStreamServerFactory`, as they are included in the required version of
  Twisted. (#88)


Misc
----

- #89


0.7.1 (2013-01-12)
==================

Features
--------

- wokkel.generic.Request.parseRequest is a new convenience hook for parsing
  the payload of incoming requests using fromElement.
- wokkel.xmppim.RosterItem can now represent item removals and has methods
  for XML (de-)serialization (#71).
- wokkel.xmppim.RosterRequest is a new class to represent roster request
  stanzas (#71).
- wokkel.xmppim.RosterClientProtocol.getRoster now returns the roster
  indexed by JID (#71).
- wokkel.xmppim.RosterClientProtocol uses the new RosterRequest for sending
  outgoing requests, using the new request semantics (#71).
- wokkel.xmppim.RosterClientProtocol uses the new RosterRequest to provide
  access to addressing and roster version information in the new callbacks
  for roster pushes (#71).
- wokkel.xmppim.RosterPushIgnored can be raised for unwanted roster pushes
  (#71).
- wokkel.xmppim.RosterClientProtocol and RosterRequest now support roster
  versioning.
- With the new wokkel.xmppim.RosterClientProtocol.setItem roster items can
  be added or updated (#56).

Fixes
-----

- wokkel.component.Component now reconnects if first attempt failed (#75).
- wokkel.xmppim.RosterClientProtocol now properly checks sender addresses
  for roster pushes (#71).
- Make sure twistd plugins are installed properly (#76).
- wokkel.component.Router.route now sends back an error if there is no known
  route to the stanza's destination.
- Properly encode IDN domain names for establishing client and server
  connections. This resolves an issue with Twisted 12.3.0 that made it
  impossible to initiate any connection using Wokkel (#77).

Deprecations
------------
- wokkel.xmppim.RosterItem.jid is deprecated in favor of entity (#71).
- wokkel.xmppim.RosterItem.ask is deprecated in favor of pendingOut (#71).
- wokkel.xmppim.RosterClientProtocol.onRosterSet is deprecated in favor of
  setReceived (#71).
- wokkel.xmppim.RosterClientProtocol.onRosterRemove is deprecated in favor
  of removeReceived (#71).


0.7.0 (2012-01-23)
==================

Features
--------

- Added method wokkel.data_form.Form.typeCheck for type checking incoming Data
  Forms submissions against field definitions.
- Added method wokkel.data_form.Form.makeFields to add fields from a
  dictionary mapping field names to values.
- Added public function wokkel.data_form.findForm for extracting Data Forms
  from stanzas.
- PubSubRequest.options is now a wokkel.data_form.Form.
- wokkel.data_form.Form can now be used as a read-only dictionary.
- Added support for configuration options in Publish-Subscribe node create
  requests.
- Added support for subscription options in Publish-Subscribe subscribe
  requests (#63).
- Added support for Publish Subscribe subscription identifiers.
- wokkel.pubsub.Item can now be used to send out notifications, too.
- Added a twistd plugin to set up a basic XMPP server that accepts component
  connections and provides server-to-server (dialback) connectivity.
- Added support for managing affiliations of Publish-Subscribe nodes,
  server-side.
- Added iq request (set/get) tracking to StreamManager and provide a new base
  class for such requests: wokkel.generic.Request. Unlike
  twisted.words.protocols.jabber.xmlstream.IQ, Such requests can be queued
  until the connection is initialized, with timeouts running from the moment
  `request` was called (instead of when it was sent over the wire).
- Added support for Delayed Delivery information formats.
- Added support for XMPP Multi-User Chat, client side (#24).

Fixes
-----

- XMPP Ping handler now marks incoming ping requests as handled, so the
  FallbackHandler doesn't respond, too. (#66)
- Incorporate Twisted changes for component password hashes.
- Completed test coverage for Data Forms.
- Made sure Data Forms field labels don't get overwritten (#60).
- Service Discovery identity is now reported correctly for legacy
  PubSubService use (#64).
- Various smaller Service Discovery fixes for PubSubService.
- Completed test coverage for Service Discovery support.
- Publish Subscribe events with stanza type error are now ignored (#69).
- Publish Subscribe requests with multiple 'verbs' are now properly parsed
  (#72).
- Publish Subscribe requests that have no legacy support in PubSubService will
  now result in a feature-not-implemented error (#70).
- Publish Subscribe subscription elements now have the correct namespace when
  sent out.
- Incorporated Twisted changes for passing on a reason Failure upon stream
  disconnect.
- Fixed race condition and nesting issues when adding subprotocol handlers to
  their StreamManager (#48).
- Reimplemented Service Discovery requests using new Request class. By reusing
  common code, this fixes a problem with requests without addressing (#73).

Deprecations
------------

- wokkel.compat.BootstrapMixin is deprecated in favor of
  twisted.words.xish.xmlstream.BootstrapMixin (Twisted 8.2.0).
- wokkel.compat.XmlStreamServerFactory is deprecated in favor of
  twisted.words.protocols.jabber.xmlstream.XmlStreamServerFactory (Twisted
  8.2.0).
- wokkel.iwokkel.IXMPPHandler is deprecated in favor of
  twisted.words.protocols.jabber.ijabber.IXMPPHandler (Twisted 8.1.0).
- wokkel.iwokkel.IXMPPHandlerCollection is deprecated in favor of
  twisted.words.protocols.jabber.ijabber.IXMPPHandlerCollection (Twisted
  8.1.0).
- wokkel.subprotocols.XMPPHandlerCollection is deprecated in favor of
  twisted.words.protocols.jabber.xmlstream.XMPPHandlerCollection (Twisted
  8.1.0).


0.6.3 (2009-08-20)
==================

Features
--------

- Add a jid attribute to XMPPClient (#18).
- Add a better presence protocol handler PresenceProtocol. This handler
  is also useful for component or in-server use.

Fixes
-----

- Use fallback port 5222 for failed SRV lookups for clients (#26).


0.6.2 (2009-07-08)
==================

Features
--------

- Add support for XMPP Ping (XEP-0199), doubling as example protocol
  handler (#55).
- Provide examples for setting up clients, components and servers (#55).
- Make Service Discovery support accept non-deferred results from getDiscoInfo
  and getDiscoItems (#55).


0.6.1 (2009-07-06)
==================

Features
--------

- Add an optional sender parameter for Service Discovery requests (#52).

Fixes:
------

- Fix regression in DeferredClientFactory (#51).
- Make IQ timeouts work with InternalComponent (#53).


0.6.0 (2009-04-22)
==================

Features
--------

- Server-to-server support, based on the dialback protocol (#33).
- Enhancement to InternalProtocol to support multiple domains (#43).
- Publish-subscribe request abstraction (#45).
- Publish-subscribe abstraction to implement a node in code (#47).
- Enhancement to PubSubClient to send requests from a specific JID (#46).

Fixes
-----

- Remove type interpretation in Data Forms field parsing code (#44).


0.5.0 (2009-04-07)
==================

This release drops support for Twisted versions older than 8.0, including
Twisted 2.5 / Twisted Words 0.5.

Features
--------

- Support for sending and receiving Publish-Subscribe node delete
  notifications with redirect.
- Service Discovery client support, including an overhaul of disco data
  classes (#28).
- Initial support for building XMPP servers has been added:

  - XmlStreamServerFactory has been backported from Twisted Words (#29).
  - An XMPP router has been added (#30).
  - A server-side component authenticator has been added (#30).
  - A new server-side component service, that connects to a router within the
    same process, was added (#31).


Fixes
-----

- Publish-Subscribe subscriptions requests work again (#22).
- Publish-Subscribe delete node requests now have the correct namespace (#27).
- NodeIDs in Service Discovery requests are now returned in responses (#7).
- The presence of stanzaType in toResponse is now checked correctly (#34).
- Data Form fields are now rendered depending on form type (#40).
- Data Form type checking issues were addressed (#41).
- Some compatibility fixes for Twisted 8.0 and 8.1.
- Various other fixes (#37, #42) and tracking changes to code already in
  Twisted.


0.4.0 (2008-08-05)
==================

- Refactoring of Data Forms support (#13).
- Added support for Stanza Headers and Internet Metadata (SHIM) (#14).
- API change for PubSubClient's methods called upon event reception (#14).
- Added client-side support for removing roster items.
- Implement type checking for data forms (#15).
- Added support for publish-subscribe collections:

  - Correct handling for the root node (empty node identifier).
  - Send out SHIM 'Collection' header when appropriate.
  - New Subscription class for working with subscriptions.
  - API change for PubSubService:

    - The subscribe method returns a deferred that fires a Subscription
    - The subscriptions method returns a deferred that fires a list of
      Subscriptions.
    - notifyPublish's notifications parameter now expects a list of tuples
      that includes a list of subscriptions.

- Added PubSubService.notifyDelete to allow sending out node deletion
  notifications.


0.3.1 (2008-04-22)
==================

- Fix broken version request handler.


0.3.0 (2008-04-21)
==================

First release.
