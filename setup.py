#!/usr/bin/env python

# Copyright (c) Ralph Meijer.
# See LICENSE for details.

from setuptools import setup

# Make sure 'twisted' doesn't appear in top_level.txt

try:
    from setuptools.command import egg_info
    egg_info.write_toplevel_names
except (ImportError, AttributeError):
    pass
else:
    def _top_level_package(name):
        return name.split('.', 1)[0]

    def _hacked_write_toplevel_names(cmd, basename, filename):
        pkgs = dict.fromkeys(
            [_top_level_package(k)
                for k in cmd.distribution.iter_distribution_names()
                if _top_level_package(k) != "twisted"
            ]
        )
        cmd.write_file("top-level names", filename, '\n'.join(pkgs) + '\n')

    egg_info.write_toplevel_names = _hacked_write_toplevel_names

setup(name='wokkel',
      version='0.7.1',
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
