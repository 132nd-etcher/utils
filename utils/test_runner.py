# coding=utf-8

import pytest
import os
from utils import make_logger, create_temp_file, create_new_paste


logger = make_logger(__name__)


def run_test(
        package: str,
        show_slow: int = None,
        show_locals: bool = False,
        upload_result: bool = False,
        upload_failed: bool = False,
    ):
    """
    :param package: package containing the test suite, as a str
    :param show_slow: number of slowest tests to show, or None
    :param show_locals: show local variables, default to False
    :param upload_failed:
    :param upload_result:
    """
    path = create_temp_file()
    args = ['--pyargs', package, '--resultlog={}'.format(path.abspath())]
    if show_slow:
        args.append('--duration={}'.format(show_slow))
    if show_locals:
        args.append('-l')
    ret = pytest.main(args)
    link = None
    if ret == 0:
        if upload_result:
            link = create_new_paste(path.text())
    else:
        if upload_failed or upload_result:
            link = create_new_paste(path.text())
    os.remove(path)
    return ret == 0, link


if __name__ == '__main__':

    def hook(url):
        print('url', url)

    ret = run_test('utils.tests', 5, False, True)
    print(ret)
