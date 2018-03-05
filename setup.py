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

with open('README.rst', 'r') as f:
    long_description = f.read()

setup(name='wokkel',
      description='Twisted Jabber support library',
      long_description = long_description,
      author='Ralph Meijer',
      author_email='ralphm@ik.nu',
      maintainer_email='ralphm@ik.nu',
      url='https://wokkel.ik.nu/',
      license='MIT',
      platforms='any',
      classifiers=[
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
      ],
      packages=[
          'wokkel',
          'wokkel.test',
          'twisted.plugins',
      ],
      package_data={'twisted.plugins': ['twisted/plugins/server.py']},
      zip_safe=False,
      setup_requires=[
          'incremental>=16.9.0',
      ],
      use_incremental=True,
      install_requires=[
          'incremental>=16.9.0',
          'python-dateutil',
      ],
      extras_require={
          ":python_version<'3'": 'Twisted[tls]>=15.5.0',
          ":python_version>'3'": 'Twisted[tls]>=16.4.0',
          "dev": [
              "pyflakes",
              "coverage",
              "pydoctor",
              "sphinx",
              "towncrier",
          ],
      },
)
