#!/usr/bin/env python

from __future__ import with_statement
try:
        from setuptools import setup
except ImportError:
        # Distribute is not actually required to install
        from distutils.core import setup

setup(name='python-langserver',
      version='0.0.1',
      description='An implementation of the Language Server Protocol for Python',
      author='Sourcegraph',
      author_email='hi@sourcegraph.com',
      include_package_data=True,
      maintainer='Sourcegraph',
      maintainer_email='hi@sourcegraph.com',
      url='https://github.com/sourcegraph/python-langserver',
      license='MIT',
      keywords='python lsp',
      packages=['langserver'],
      platforms=['any'],
      install_requires=[
              'opentracing',
              'lightstep',
              'jedi',
              'pip',
      ],
      dependency_links=[
              'git+https://github.com/sourcegraph/pip.git@94070088f5c458802c83bab37e704365b041acd8#egg=pip',
              'git+https://github.com/sourcegraph/jedi.git@9a3e7256df2e6099207fd7289141885ec17ebec7#egg=jedi',
      ],
)
