# coding=utf-8

import logging
import pytest


@pytest.fixture(scope='session', autouse=True)
def disable_logging():
    logging.disable(logging.ERROR)