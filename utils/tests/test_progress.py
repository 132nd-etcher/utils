# coding=utf-8

import pytest
from utils import Progress, ProgressAdapter, Singleton
from hypothesis import given
from hypothesis.strategies import text, integers

not_a_string = [int(0), None, True, float(3.5)]
not_an_int = ['text', None, float(3.5)]  # not including bool because it's an instance of int


class TestProgressAdapter(ProgressAdapter):
    def set_value(self, value: int):
        pass

    def start(self, title: str, length: int = 100, label: str = ''):
        pass

    def done(self):
        pass

    @property
    def name(self) -> str:
        return 'test_progress_adapter'

    def set_label(self, value: str):
        pass

    def __init__(self):
        super(TestProgressAdapter, self).__init__()


class TestProgress:

    @pytest.fixture(scope='function', autouse=True)
    def wipe_singleton(self):
        Singleton.wipe_instances('Progress')

    @pytest.fixture('function')
    def progress_with_adapter(self):
        self.wipe_singleton()
        adapter = TestProgressAdapter()
        Progress().register_adapter(adapter)
        return Progress(), adapter

    @pytest.fixture('function')
    def progress(self):
        self.wipe_singleton()
        yield Progress()

    def set_correct(self, value, attrib):
        progress, _ = self.progress_with_adapter()
        assert isinstance(progress, Progress)
        setattr(progress, attrib, value)
        assert getattr(progress, attrib) == value

    def set_wrong(self, value, attrib):
        progress, _ = self.progress_with_adapter()
        assert isinstance(progress, Progress)
        with pytest.raises(TypeError):
            setattr(progress, attrib, value)

    def set_both(self, attrib, correct_value, wronge_value):
        self.set_correct(correct_value, attrib)
        self.set_wrong(wronge_value, attrib)

    def test_start(self, progress_with_adapter):
        progress, adapter = progress_with_adapter
        progress.start(title='title')
        assert adapter.name == 'test_progress_adapter'
        assert progress.title == 'title'
        assert progress.label == ''
        assert progress.length == 100
        assert progress.value == 0

    def test_double_start(self, progress_with_adapter):
        progress, _ = progress_with_adapter
        progress.start('test')
        with pytest.raises(RuntimeError):
            progress.start('test')

    def test_is_started(self, progress_with_adapter):
        progress, _ = progress_with_adapter
        progress.start('test')
        assert progress.length == 100
        assert progress.is_started
        progress.value = 50
        assert progress.is_started
        progress.value = 100
        assert progress.is_started is False

    @pytest.mark.parametrize('wrong_value', not_a_string)
    @given(correct_value=text())
    def test_label(self, correct_value, wrong_value):
        self.set_both('label', correct_value, wrong_value)

    @pytest.mark.parametrize('wrong_value', not_a_string)
    @given(correct_value=text())
    def test_title(self, correct_value, wrong_value):
        self.set_both('title', correct_value, wrong_value)

    @pytest.mark.parametrize('wrong_value', not_an_int)
    @given(correct_value=integers(min_value=0, max_value=100))
    def test_value(self, correct_value, wrong_value):
        self.set_both('value', correct_value, wrong_value)
        with pytest.raises(ValueError):
            Progress().value = Progress().length + 1

    @pytest.mark.parametrize('wrong_value', not_an_int)
    @given(correct_value=integers(min_value=1, max_value=100))
    def test_length(self, correct_value, wrong_value):
        self.set_both('length', correct_value, wrong_value)
        with pytest.raises(ValueError):
            Progress().length = -1

    def test_adapter(self):

        class OtherAdapter(TestProgressAdapter):

            @property
            def name(self):
                return 'other_adapter'

        adapter = TestProgressAdapter()
        other_adapter = OtherAdapter()
        progress = Progress(adapters=[adapter, other_adapter])
        assert adapter in progress._adapters
        assert progress.has_adapter('test_progress_adapter') is True
        assert progress.has_adapter(adapter)
        assert progress.has_adapter(other_adapter)
        assert progress.has_adapter('test_progress_adapter')
        assert progress.has_adapter('other_adapter')

        progress.unregister_adapter(other_adapter)
        assert not progress.has_adapter('other_adapter')

        progress.unregister_adapter(adapter)
        assert not progress.has_adapter(adapter)

        progress.register_adapter(adapter)
        assert progress.has_adapter('test_progress_adapter') is True
        progress.unregister_adapter('test_progress_adapter')
        assert not progress.has_adapter('test_progress_adapter')

        assert not progress.unregister_adapter('i_don_t_exist')

    @pytest.mark.parametrize('adapter', [None, True, 'test', 1])
    def test_wrong_adapter_init(self, adapter):
        with pytest.raises(TypeError):
            Progress(adapters=[adapter])

    @pytest.mark.parametrize('adapter', [None, True, 'test', 1])
    def test_wrong_adapter_register(self, adapter):
        with pytest.raises(TypeError):
            Progress().register_adapter(adapter)

    def test_adapter_double_register(self, progress_with_adapter):
        progress, adapter = progress_with_adapter
        with pytest.raises(RuntimeError):
            progress.register_adapter(adapter)



