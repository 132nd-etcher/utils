# coding=utf-8

import time
import functools

from .custom_logging import make_logger, Logged
from .validator import not_a_bool, not_a_positive_int, not_a_str, not_an_int, valid_bool, valid_float, valid_str, \
    valid_dict, valid_existing_path, valid_int, valid_list, valid_negative_int, valid_positive_int, Validator
from .custom_path import Path, create_temp_file, create_temp_dir
from .downloader import Downloader
from .progress import Progress, ProgressAdapter
from .singleton import Singleton
from .updater import Updater, Version, GithubRelease
from .threadpool import ThreadPool
from .decorators import TypedProperty
from .pastebin import create_new_paste
from .monkey import nice_exit


def clock(func):
    @functools.wraps(func)
    def clocked(*args, **kwargs):
        t0 = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - t0
        name = func.__name__
        arg_lst = []
        if args:
            arg_lst.append(', '.join(repr(arg) for arg in args))
        if kwargs:
            pairs = ['%s=%r' % (k, w) for k, w in sorted(kwargs.items())]
            arg_lst.append(', '.join(pairs))
        arg_str = ', '.join(arg_lst)
        print('[%0.8fs] %s(%s) -> %r ' % (elapsed, name, arg_str, result))
        return result
    return clocked

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
