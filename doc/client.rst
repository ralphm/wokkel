XMPP Clients
============

Wokkel supports two different approaches to create XMPP client applications,
one for persistent connections and one for one-off purposes. This builds
further on the XMPP client functionality that is provided by Twisted Words,
while providing support for so-called :term:`subprotocols`.

Persistent Clients
------------------

Persistent clients are meant to be used for extended periods, where the
application wants to exchange communications with other entities. Instances of
:api:`wokkel.client.XMPPClient <XMPPClient>` are Twisted services that connect
to an XMPP server and act as a stream manager that can be assigned as the
parent of subprotocol implementations.

Basic XMPP client
^^^^^^^^^^^^^^^^^

The following example creates the most basic XMPP client as a `Twisted
Application
<http://twistedmatrix.com/projects/core/documentation/howto/application.html>`_.

.. literalinclude:: listings/client/client1.tac
   :language: python
   :linenos:

First we create the application object, to later add services to. The XMPP
client service is passed a ``JID`` instance and the associated password as
login credentials to the server. This assumes that the server is set up
properly, so that the client can connect to the server by extracting the domain
name from the JID and retrieving the server's address by resolving it through
DNS (optionally by using SRV records). To see what is exchanged between the
client and server, we enable traffic logging. Finally, we set the application
object as the parent of the XMPP client service. This ensures that the service
gets started properly.

The client can be started with the command ``twistd -noy client.tac``. The
application will start while logging to the terminal it was started from,
including the traffic log we enabled. The final lines should look similar to
this for a regular XMPP server::

    ...
    2008-02-29 14:21:08+0100 [XmlStream,client] SEND: "<iq type='set' id='H_1'><session xmlns='urn:ietf:params:xml:ns:xmpp-session'/></iq>"
    2008-02-29 14:21:08+0100 [XmlStream,client] RECV: '<iq type="result" id="H_1" to="test@example.org/ca05ba89"><session xmlns="urn:ietf:params:xml:ns:xmpp-session"/></iq>'

This client does not do much beyond logging into the server, and we can shut it
down by pressing ``CTRL-C``.

Adding a subprotocol handler
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The next step is to add a subprotocol handler to the client, the presence
handler:

.. literalinclude:: listings/client/client2.tac
   :language: python
   :linenos:

The :api:`wokkel.xmppim.PresenceProtocol <PresenceProtocol>` instance has a
number of methods for sending presence, but can also be subclassed to process
incoming presence from contacts. For now we just add the handler to our client
by setting the handler's parent to the client service. Then we ask it to send
available presence. Although we are not connected at this point yet, the
corresponding message will be stored by the client service and sent as soon as
we have successfully connected and authenticated.

One-off clients
---------------

Sometimes, you just want a client that logs in, do a short task, log out again
and stop the application. For this, wokkel has the
:api:`wokkel.client.DeferredClientFactory <DeferredClientFactory>`. As the name
suggests, it is based on working with deferreds. In the following example we
create a subprotocol handler for inquiring a server for what software and the
version it is running.

.. literalinclude:: listings/client/one_off_client.tac
   :language: python
   :linenos:

In this example we dive a little deeper in the XMPP protocol handling. Instead
of using the more polished :api:`wokkel.client.XMPPClient <XMPPClient>`, we
create a protocol factory that is responsible for handling the protocol once a
connection has been made, including logging in and setting up a stream manager.
The :api:`wokkel.client.clientFactory <clientFactory>` however is responsible
for establishing the connection. When it does, and the connection has been
initialized (which includes authentication), the returned deferred will be
fired. In case of a connection or initialization error, the deferred will have
its errback called instead.

We can now use this deferred to add callbacks for our one-time tasks. The first
callback we add is ``getVersion``, while using a lambda construct to ignore the
result of the callback. We pass the object that represents the XML stream, as
stored in the factory's stream manager. This is needed for tracking the
response to the version query. The second parameter is the JID that we want to
send the version request to, in this case, the server that holds the account we
login with.

The second callback uses the result from the version request, a dictionary with
the keys ``name`` and ``version`` to hold the software name and version strings
as reported by our server. Having been passed this dictionary, ``printVersion``
prints the information to the terminal. The third callback neatly closes the
stream. In case of any error, the added errback handler just logs it and
finally we add a callback that is always called, shutting down the application
after one second.
