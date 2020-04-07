#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from setuptools import setup, find_packages
import abejacli.version


def _load_requires_from_file(filepath):
    return [pkg_name.rstrip('\r\n') for pkg_name in open(filepath).readlines()]


def _install_requires():
    requires = _load_requires_from_file('requirements.txt')
    return requires


if __name__ == '__main__':
    description = ''
    setup(
        name='abejacli',
        version=abejacli.version.VERSION,
        description=description,
        author='ABEJA Inc.',
        author_email='platform-support@abejainc.com',
        classifiers=[
        ],
        packages=find_packages(exclude=["tests.*", "tests"]),
        package_data={
            'abejacli': [
                'template/*'
            ],
        },
        install_requires=_install_requires(),
        include_package_data=True,
        zip_safe=False,
        entry_points="""
        [console_scripts]
        abeja = abejacli.run:main
        """,
    )
