# Copyright (c) 2003-2010 Ralph Meijer
# See LICENSE for details.

from twisted.application.service import ServiceMaker

WokkelXMPPComponentServer = ServiceMaker(
    "XMPP Component Server",
    "wokkel.componentservertap",
    "An XMPP Component Server",
    "wokkel-component-server")
