#!/usr/bin/env python

# Copyright (c) Ralph Meijer.
# See LICENSE for details.

from setuptools import setup

setup(name='wokkel',
      version='0.7.0',
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
          'twisted.plugins',
      ],
      package_data={'twisted.plugins': ['twisted/plugins/server.py']},
      zip_safe=False,
      install_requires=[
          'Twisted >= 10.0.0',
          'python-dateutil',
      ],
)
