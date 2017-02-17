# coding=utf-8

import pytest
from httmock import HTTMock

from utils import Path, Downloader, Progress
from utils.updater import Version, Updater, GithubRelease
from .test_gh import mock_gh_api, GHRelease

valid_versions = {
    '0.0.0+1': {
        'channel': 'stable',
        'branch': None,
    },
    '0.0.0-dev.13': {
        'channel': 'dev',
        'branch': None,
    },
    '0.0.0-alpha.test.15': {
        'channel': 'alpha',
        'branch': 'test',
    },
    '0.0.0-beta.test.15': {
        'channel': 'beta',
        'branch': 'test',
    },
    '0.0.0-rc.15': {
        'channel': 'rc',
        'branch': None,
    },
}

valid_versions = [(
                      k,
                      valid_versions[k]['channel'],
                      valid_versions[k]['branch'],
                  ) for k in valid_versions]

ordered_versions = [
    '0.0.0-alpha.test.15',
    '0.0.0-beta.test.15',
    '0.0.0-dev.13',
    '0.0.0',
    '0.0.1-alpha.test.15',
    '0.0.1-alpha.test.16',
    '0.0.1',
]

same_versions = [
    ('0.0.0-alpha.test.15', '0.0.0-alpha.test.15+1'),
    ('0.0.0-dev.1', '0.0.0-dev.1+some-text'),
    ('0.0.1', '0.0.1+15-some-text'),
]

wrong_version_string = [
    '0.0',
    '0.0.0.0',
    '0+0.0',
    '0.0.1-alpha+test.15',
]


class TestVersion:
    @pytest.mark.parametrize('version_str, channel, branch', valid_versions)
    def test_init(self, version_str, channel, branch):
        version = Version(version_str)
        assert version.channel == channel
        assert version.branch == branch
        assert str(version) == version_str

    @pytest.mark.parametrize('version', wrong_version_string)
    def test_wrong_init(self, version):
        with pytest.raises(ValueError):
            Version(version)

    def test_ordering(self):
        for i in range(len(ordered_versions) - 1):
            assert Version(ordered_versions[i]) < Version(ordered_versions[i + 1])
            assert Version(ordered_versions[i + 1]) > Version(ordered_versions[i])
        for x in same_versions:
            assert Version(x[0]) == Version(x[1])


updater_version = [
    ('0.0.1', 'stable', True),
    ('0.0.2', 'stable', False),
    ('0.0.2', 'dev', True),
    ('0.0.3', 'dev', False),
    ('0.0.3', 'beta', True),
    ('0.0.4', 'beta', False),
    ('0.0.4', 'alpha', True),
    ('0.0.6', 'alpha', False),
]

dummy_gh_release = [
    ({"tag_name": "0.0.1"}, '0.0.1', 'stable', None),
    ({"tag_name": "0.0.2-alpha.test.1"}, '0.0.2-alpha.test.1', 'alpha', 'test'),
    ({"tag_name": "0.0.2-beta.test.1+532"}, '0.0.2-beta.test.1', 'beta', 'test'),
    ({"tag_name": "0.0.3-rc.1"}, '0.0.3-rc.1', 'rc', None),
]

dummy_gh_assets = [
    (
        {"tag_name": "0.0.1",
         "assets":
             [
                 {"browser_download_url": "the_url", "name": "example.zip"},
             ]
         },
        'example.zip', 'the_url'
    ),
    (
        {"tag_name": "0.0.1",
         "assets":
             [
                 {"browser_download_url": "the_url1", "name": "EXAMPLE1"},
                 {"browser_download_url": "the_url2", "name": "EXAMPLE2"},
                 {"browser_download_url": "the_url3", "name": "EXAMPLE3"},
                 {"browser_download_url": "the_url4", "name": "EXAMPLE4"},
             ]
         },
        'example3', 'the_url3'
    ),
]

dummy_candidates = {
    '0.0.2': GithubRelease(GHRelease({"tag_name": "0.0.2"})),
    '0.0.1': GithubRelease(GHRelease({"tag_name": "0.0.1"})),
    '0.0.3': GithubRelease(GHRelease({"tag_name": "0.0.3"})),
    '0.0.4': GithubRelease(GHRelease({"tag_name": "0.0.4"})),
}


class TestUpdater:
    def test_no_release(self, tmpdir):
        p = Path(tmpdir.join('test.exe'))
        upd = Updater(p.abspath(), '0.0.1', '132nd-etcher', 'no_release', 'example.zip')

        with HTTMock(mock_gh_api):
            upd._get_available_releases()
            assert not upd.available

    def test_pre_hook_is_false(self, tmpdir, mocker):
        def pre_hook():
            return False

        post_hook = mocker.MagicMock()

        p = Path(tmpdir.join('test.exe'))
        upd = Updater(p.abspath(), '0.0.1', '132nd-etcher', 'EASI', 'example.zip', pre_hook, post_hook)

        with HTTMock(mock_gh_api):
            upd._version_check('alpha')
            assert upd.available
            assert upd._process_candidates() is False
            post_hook.assert_called_once_with()

        upd = Updater(p.abspath(), '0.0.1', '132nd-etcher', 'EASI', 'example.zip', pre_hook)

        with HTTMock(mock_gh_api):
            upd._version_check('alpha')
            assert upd.available
            assert upd._process_candidates() is False

    # @pytest.mark.parametrize('candidates', dummy_candidates)
    def test_process_candidates(self, tmpdir):
        p = Path(tmpdir.join('test.exe'))

        upd = Updater(p.abspath(), '0.0.1', '132nd-etcher', 'EASI', 'example.zip')

        upd._candidates = dummy_candidates
        assert upd._process_candidates() is True

        upd._current = Version('0.0.5')
        assert upd._process_candidates() is False

    @pytest.mark.parametrize('gh_release', dummy_gh_release)
    def test_gh_release(self, gh_release):

        json, version_str, channel, branch = gh_release

        gh_rel = GithubRelease(GHRelease(json))
        assert gh_rel.version == Version(version_str)
        assert gh_rel.channel == channel
        assert gh_rel.branch == branch

    @pytest.mark.parametrize('gh_assets', dummy_gh_assets)
    def test_gh_release_assets(self, gh_assets):
        json, asset_name, dld_url = gh_assets
        gh_rel = GithubRelease(GHRelease(json))
        assert gh_rel.get_asset_download_url('some_asset') is None
        assert gh_rel.get_asset_download_url(asset_name) == dld_url

    @pytest.mark.parametrize('channel', ['Alpha', '_beta', 'STABLE', 'random', 1, True, None, float(3)])
    def test_wrong_channel(self, channel, tmpdir):
        p = Path(tmpdir.join('test.exe'))
        upd = Updater(p.abspath(), '0.0.1', '132nd-etcher', 'EASI', 'example.zip')
        with pytest.raises(ValueError):
            upd._version_check(channel)

    @pytest.mark.parametrize('current, channel, expected_result', updater_version)
    def test_check_version_without_hooks(self, current, channel, expected_result, tmpdir):

        p = Path(tmpdir.join('test.exe'))

        upd = Updater(
            executable_name=p.abspath(),
            current_version=current,
            gh_user='132nd-etcher',
            gh_repo='EASI',
            asset_filename='example.zip')

        with HTTMock(mock_gh_api):
            assert upd._version_check(channel) is expected_result
            upd._process_candidates()

    @pytest.mark.parametrize('current, channel, expected_result', updater_version)
    def test_check_version(self, current, channel, expected_result, tmpdir, mocker):

        pre = mocker.MagicMock()
        cancel = mocker.MagicMock()

        p = Path(tmpdir.join('test.exe'))

        upd = Updater(
            executable_name=p.abspath(),
            current_version=current,
            gh_user='132nd-etcher',
            gh_repo='EASI',
            asset_filename='example.zip',
            pre_update_func=pre,
            cancel_update_func=cancel)

        with HTTMock(mock_gh_api):

            assert upd._version_check(channel) is expected_result

            upd._process_candidates()

            if expected_result is True:

                pre.assert_called_once_with()
                assert upd._candidates
                assert upd.latest_release

                assert isinstance(upd.latest_release, GithubRelease)

                class DummyDownloader(Downloader):

                    download_return = True

                    def download(self):
                        self.progress_hooks[0]({'time': '00:00', 'downloaded': 100, 'total': 100})
                        return DummyDownloader.download_return

                mocker.patch('utils.updater.Downloader', new=DummyDownloader)

                upd._download_latest_release()
                assert upd._update_ready_to_install
                Progress.done()

                DummyDownloader.download_return = False

                upd._download_latest_release()
                cancel.assert_called_once_with()
                assert not upd._update_ready_to_install
                Progress.done()

            else:

                cancel.assert_called_once_with()
