#! /usr/bin/python
"""
pytest-dependency - Manage dependencies of tests

This pytest plugin manages dependencies of tests.  It allows to mark
some tests as dependent from other tests.  These tests will then be
skipped if any of the dependencies did fail or has been skipped.
"""

__version__ = "0.5.0"

from setuptools import setup, find_packages

setup(
    name='pytest-dependency',
    version=__version__,
    description='Manage dependencies of tests',
    author='Rolf Krahl',
    author_email='rolf@rotkraut.de',
    maintainer='Rolf Krahl',
    maintainer_email='rolf@rotkraut.de',
    url='https://github.com/RKrahl/pytest-dependency',
    license='Apache Software License 2.0',
    long_description=__doc__,
    project_urls={
        'Documentation': 'https://pytest-dependency.readthedocs.io/',
        'Source Code': 'https://github.com/SelfHacked/pytest-dependency',
    },
    python_requires='>=3.6',
    packages=find_packages(),
    install_requires=['pytest >= 3.6.0'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: Apache Software License',
    ],
    entry_points={
        'pytest11': [
            'dependency = pytest_dependency',
        ],
    },
)
