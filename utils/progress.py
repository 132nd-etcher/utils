# coding=utf-8

from utils.singleton import Singleton


class Progress(Singleton):
    
    MAIN_UI = None
    
    @staticmethod
    def register_main_ui(main_ui):
        Progress.MAIN_UI = main_ui

    @staticmethod
    def __wrapper(func_name, *args, **kwargs):
        if Progress.MAIN_UI:
            Progress.MAIN_UI.do('main_ui', func_name, *args, **kwargs)
    
    @staticmethod
    def start(title: str, length: int, label: str = ''):
        Progress.__wrapper('progress_start', title, length, label)

    @staticmethod
    def set_value(value: int):
        Progress.__wrapper('progress_set_value', value)

    @staticmethod
    def set_label(value: str):
        Progress.__wrapper('progress_set_label', value)

    @staticmethod
    def done():
        Progress.__wrapper('progress_done')
