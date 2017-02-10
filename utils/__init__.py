# coding=utf-8

from .custom_logging import make_logger, Logged
from .validator import not_a_bool, not_a_positive_int, not_a_str, not_an_int, valid_bool, valid_float, valid_str, \
    valid_dict, valid_existing_path, valid_int, valid_list, valid_negative_int, valid_positive_int, Validator
from .custom_path import Path
from .downloader import Downloader
from .progress import Progress
from .singleton import Singleton
from .updater import Updater
from .threadpool import ThreadPool


def nice_exit(*_):
    import os
    # Shameful monkey-patching to bypass windows being a jerk
    # noinspection PyProtectedMember
    os._exit(0)
