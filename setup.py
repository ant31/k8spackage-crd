#!/usr/bin/env python
# -*- coding: utf-8 -*-


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


with open('README.md') as readme_file:
    readme = readme_file.read()


requirements = [
    'futures',
    'future',
    'requests',
    'pyyaml',
    'pathspec',
    'urllib3[secure]'
]

test_requirements = [
    "pytest",
    "coverage",
    "pytest-sugar",
    "pytest-cov",
    "pytest-ordering",
    "requests-mock"
]

setup(
    name='k8spackage',
    version='0.1.0',
    description="k8spackage",
    long_description=readme,
    author="Antoine Legrand",
    author_email='2t.antoine@gmail.com',
    url='https://github.com/ant31/k8spackage',
    packages=[
        'k8spackage',
        'k8spackage.commands',
        'k8spackage.commands.generate'
    ],
    package_dir={'k8spackage':
                 'k8spackage'},
    include_package_data=True,
    scripts=['bin/k8s-package'],
    install_requires=requirements,
    license="Apache License version 2",
    zip_safe=False,
    keywords=['k8spackage'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
    ],
    test_suite='tests',
    tests_require=test_requirements,
)
