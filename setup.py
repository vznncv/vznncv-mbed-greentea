#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re

from setuptools import setup, find_packages

project_name = 'vznncv-mbed-greentea'

with open('README.md') as readme_file:
    readme = readme_file.read()
readme = re.sub(r'!\[[^\[\]]*\]\S*', '', readme)

_locals = {}
with open('src/' + project_name.replace('-', '/') + '/_version.py') as fp:
    exec(fp.read(), None, _locals)
__version__ = _locals['__version__']

with open('requirements_dev.txt') as fp:
    test_requirements = fp.read()

setup(
    author="Konstantin Kochin",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Embedded Systems",
    ],
    python_requires='>=3.6',
    description="CMake project generator from STM32CubeMX project",
    long_description=readme,
    long_description_content_type="text/markdown",
    license='MIT',
    include_package_data=True,
    name=project_name,
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    entry_points={
        "console_scripts": [
            "vznncv-mbedgtw = vznncv.mbed.greentea._cli:main",
        ]
    },
    install_requires=[
        'click>=7.1.2',
        # 'mbed-cli>=1.10.4,<2',
        # due active monkey patches fix "mbed-os-tools" versions
        'mbed-os-tools==0.0.15',
        'mbed-ls==1.7.12',
        'mbed-host-tests==1.5.10',
        'mbed-greentea==1.7.4'
    ],
    tests_require=test_requirements,
    version=__version__
)
