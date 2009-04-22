#!/usr/bin/env python

# Copyright (c) 2003-2009 Ralph Meijer
# See LICENSE for details.

from setuptools import setup

setup(name='wokkel',
      version='0.6.0',
      description='Twisted Jabber support library',
      author='Ralph Meijer',
      author_email='ralphm@ik.nu',
      maintainer_email='ralphm@ik.nu',
      url='http://wokkel.ik.nu/',
      license='MIT',
      platforms='any',
      packages=[
          'wokkel',
          'wokkel.test',
      ],
)
