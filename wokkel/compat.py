# -*- test-case-name: wokkel.test.test_compat -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Compatibility module to provide backwards compatibility with Twisted features.
"""

__all__ = ['BootstrapMixin', 'XmlStreamServerFactory', 'IQ',
           'NamedConstant', 'ValueConstant', 'Names', 'Values']

from itertools import count

from twisted.internet import protocol
from twisted.words.protocols.jabber import xmlstream

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



class IQ(xmlstream.IQ):
    def __init__(self, *args, **kwargs):
        # Make sure we have a reactor parameter
        try:
            reactor = kwargs['reactor']
        except KeyError:
            from twisted.internet import reactor
        kwargs['reactor'] = reactor

        # Check if IQ's init accepts the reactor parameter
        try:
            xmlstream.IQ.__init__(self, *args, **kwargs)
        except TypeError:
            # Guess not. Remove the reactor parameter and try again.
            del kwargs['reactor']
            xmlstream.IQ.__init__(self, *args, **kwargs)

            # Patch the XmlStream instance so that it has a _callLater
            self._xmlstream._callLater = reactor.callLater



_unspecified = object()
_constantOrder = count().next


class _Constant(object):
    """
    @ivar _index: A C{int} allocated from a shared counter in order to keep
        track of the order in which L{_Constant}s are instantiated.

    @ivar name: A C{str} giving the name of this constant; only set once the
        constant is initialized by L{_ConstantsContainer}.

    @ivar _container: The L{_ConstantsContainer} subclass this constant belongs
        to; only set once the constant is initialized by that subclass.
    """
    def __init__(self):
        self._index = _constantOrder()


    def __get__(self, oself, cls):
        """
        Ensure this constant has been initialized before returning it.
        """
        cls._initializeEnumerants()
        return self


    def __repr__(self):
        """
        Return text identifying both which constant this is and which collection
        it belongs to.
        """
        return "<%s=%s>" % (self._container.__name__, self.name)


    def _realize(self, container, name, value):
        """
        Complete the initialization of this L{_Constant}.

        @param container: The L{_ConstantsContainer} subclass this constant is
            part of.

        @param name: The name of this constant in its container.

        @param value: The value of this constant; not used, as named constants
            have no value apart from their identity.
        """
        self._container = container
        self.name = name



class _EnumerantsInitializer(object):
    """
    L{_EnumerantsInitializer} is a descriptor used to initialize a cache of
    objects representing named constants for a particular L{_ConstantsContainer}
    subclass.
    """
    def __get__(self, oself, cls):
        """
        Trigger the initialization of the enumerants cache on C{cls} and then
        return it.
        """
        cls._initializeEnumerants()
        return cls._enumerants



class _ConstantsContainer(object):
    """
    L{_ConstantsContainer} is a class with attributes used as symbolic
    constants.  It is up to subclasses to specify what kind of constants are
    allowed.

    @cvar _constantType: Specified by a L{_ConstantsContainer} subclass to
        specify the type of constants allowed by that subclass.

    @cvar _enumerantsInitialized: A C{bool} tracking whether C{_enumerants} has
        been initialized yet or not.

    @cvar _enumerants: A C{dict} mapping the names of constants (eg
        L{NamedConstant} instances) found in the class definition to those
        instances.  This is initialized via the L{_EnumerantsInitializer}
        descriptor the first time it is accessed.
    """
    _constantType = None

    _enumerantsInitialized = False
    _enumerants = _EnumerantsInitializer()

    def __new__(cls):
        """
        Classes representing constants containers are not intended to be
        instantiated.

        The class object itself is used directly.
        """
        raise TypeError("%s may not be instantiated." % (cls.__name__,))


    def _initializeEnumerants(cls):
        """
        Find all of the L{NamedConstant} instances in the definition of C{cls},
        initialize them with constant values, and build a mapping from their
        names to them to attach to C{cls}.
        """
        if not cls._enumerantsInitialized:
            constants = []
            for (name, descriptor) in cls.__dict__.iteritems():
                if isinstance(descriptor, cls._constantType):
                    constants.append((descriptor._index, name, descriptor))
            enumerants = {}
            for (index, enumerant, descriptor) in constants:
                value = cls._constantFactory(enumerant)
                descriptor._realize(cls, enumerant, value)
                enumerants[enumerant] = descriptor
            # Replace the _enumerants descriptor with the result so future
            # access will go directly to the values.  The _enumerantsInitialized
            # flag is still necessary because NamedConstant.__get__ may also
            # call this method.
            cls._enumerants = enumerants
            cls._enumerantsInitialized = True
    _initializeEnumerants = classmethod(_initializeEnumerants)


    def _constantFactory(cls, name):
        """
        Construct the value for a new constant to add to this container.

        @param name: The name of the constant to create.

        @return: L{NamedConstant} instances have no value apart from identity,
            so return a meaningless dummy value.
        """
        return _unspecified
    _constantFactory = classmethod(_constantFactory)


    def lookupByName(cls, name):
        """
        Retrieve a constant by its name or raise a C{ValueError} if there is no
        constant associated with that name.

        @param name: A C{str} giving the name of one of the constants defined by
            C{cls}.

        @raise ValueError: If C{name} is not the name of one of the constants
            defined by C{cls}.

        @return: The L{NamedConstant} associated with C{name}.
        """
        if name in cls._enumerants:
            return getattr(cls, name)
        raise ValueError(name)
    lookupByName = classmethod(lookupByName)


    def iterconstants(cls):
        """
        Iteration over a L{Names} subclass results in all of the constants it
        contains.

        @return: an iterator the elements of which are the L{NamedConstant}
            instances defined in the body of this L{Names} subclass.
        """
        constants = cls._enumerants.values()
        constants.sort(key=lambda descriptor: descriptor._index)
        return iter(constants)
    iterconstants = classmethod(iterconstants)



class NamedConstant(_Constant):
    """
    L{NamedConstant} defines an attribute to be a named constant within a
    collection defined by a L{Names} subclass.

    L{NamedConstant} is only for use in the definition of L{Names}
    subclasses.  Do not instantiate L{NamedConstant} elsewhere and do not
    subclass it.
    """



class Names(_ConstantsContainer):
    """
    A L{Names} subclass contains constants which differ only in their names and
    identities.
    """
    _constantType = NamedConstant



class ValueConstant(_Constant):
    """
    L{ValueConstant} defines an attribute to be a named constant within a
    collection defined by a L{Values} subclass.

    L{ValueConstant} is only for use in the definition of L{Values} subclasses.
    Do not instantiate L{ValueConstant} elsewhere and do not subclass it.
    """
    def __init__(self, value):
        _Constant.__init__(self)
        self.value = value



class Values(_ConstantsContainer):
    """
    A L{Values} subclass contains constants which are associated with arbitrary
    values.
    """
    _constantType = ValueConstant

    def lookupByValue(cls, value):
        """
        Retrieve a constant by its value or raise a C{ValueError} if there is no
        constant associated with that value.

        @param value: The value of one of the constants defined by C{cls}.

        @raise ValueError: If C{value} is not the value of one of the constants
            defined by C{cls}.

        @return: The L{ValueConstant} associated with C{value}.
        """
        for constant in cls.iterconstants():
            if constant.value == value:
                return constant
        raise ValueError(value)
    lookupByValue = classmethod(lookupByValue)
