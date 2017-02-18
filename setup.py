# coding=utf-8

from setuptools import setup

# noinspection SpellCheckingInspection
install_requires = [
    'path.py',
    'urllib3',
    'humanize',
    'pypiwin32',
    'certifi',
    'semver',
    'requests']
# noinspection SpellCheckingInspection
test_requires = [
    'colorama',
    'coverage',
    'pytest',
    'pytest-mock',
    'pytest-cov',
    'pytest-runner',
    'colorama',
    'py',
    'hypothesis',
    'httmock'
]

# noinspection SpellCheckingInspection
setup(
    name='utils',
    version='0.0.10',
    author='132nd-etcher',
    url='https://github.com/132nd-etcher/utils',
    packages=['utils', 'utils.gh', 'utils.gh.gh_objects', 'utils.decorators'],
    package_data={'utils.tests': ['utils/tests/api.github.com/*']},
    install_requires=install_requires,
    test_requires=test_requires
)
