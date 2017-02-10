# coding=utf-8

from setuptools import setup

# noinspection SpellCheckingInspection
install_requires = [
    'six',
    'path.py',
    'urllib3',
    'humanize',
    'pypiwin32',
    'certifi',
    'wincertstore',
    'semver',
    'requests']
# noinspection SpellCheckingInspection
test_requires = [
    'pytest',
    'colorama',
    'py',
    'hypothesis',
    'httmock'
]

# noinspection SpellCheckingInspection
setup(
    name='utils',
    version='0.0.1',
    author='132nd-etcher',
    url='https://github.com/132nd-etcher/utils',
    packages=['utils', 'tests'],
    install_requires=install_requires,
    test_requires=test_requires
)
