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

get_latest_remote = [
    ('0.0.1', 'stable', ['0.0.2'], '0.0.2', True),
    ('0.0.2', 'stable', ['0.0.2'], '0.0.2', False),
    ('0.0.2', 'stable', ['0.0.2-dev.1'], None, False),
    ('0.0.2', 'rc', ['0.0.2-dev.1', '0.0.2-rc.1'], '0.0.2-rc.1', False),
    ('0.0.2', 'rc', ['0.0.2-dev.1', '0.0.2-rc.1', '0.0.3-rc.1'], '0.0.3-rc.1', True),
    ('0.0.2', 'dev', ['0.0.2-dev.1'], '0.0.2-dev.1', False),
    ('0.0.1', 'dev', ['0.0.2-dev.1'], '0.0.2-dev.1', True),
    ('0.0.2', 'dev', ['0.0.2-dev.1', '0.0.3-alpha.caribou.1'], '0.0.2-dev.1', False),
    ('0.0.2', 'beta', ['0.0.2-dev.1', '0.0.3-alpha.caribou.1'], '0.0.2-dev.1', False),
    ('0.0.2', 'beta', ['0.0.2-dev.1', '0.0.3-alpha.caribou.1'], '0.0.2-dev.1', False),
    ('0.0.2', 'alpha', ['0.0.2-dev.1', '0.0.3-alpha.caribou.1'], '0.0.3-alpha.caribou.1', True),
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

dummy_branches = [
    ('0.0.2-alpha.branch1.2', {
        '0.0.2-alpha.branch1.2': GithubRelease(GHRelease({"tag_name": "0.0.2-alpha.branch1.2"})),
        '0.0.2-alpha.branch2.3': GithubRelease(GHRelease({"tag_name": "0.0.2-alpha.branch2.3"})),
        '0.0.2-alpha.branch3.3': GithubRelease(GHRelease({"tag_name": "0.0.2-alpha.branch3.3"})),
    }, False),
    ('0.0.2-alpha.branch1.1', {
        '0.0.2-alpha.branch1.2': GithubRelease(GHRelease({"tag_name": "0.0.2-alpha.branch1.2"})),
    }, True),
    ('0.0.2-alpha.branch2.1', {
        '0.0.2-alpha.branch1.2': GithubRelease(GHRelease({"tag_name": "0.0.2-alpha.branch1.2"})),
    }, False),
    ('0.0.2-alpha.branch2.1', {
        '0.0.2-beta.branch1.2': GithubRelease(GHRelease({"tag_name": "0.0.2-beta.branch1.2"})),
    }, False),
    ('0.0.2-beta.branch2.1', {
        '0.0.2-beta.branch1.2': GithubRelease(GHRelease({"tag_name": "0.0.2-beta.branch1.2"})),
    }, False),
    ('0.0.2-develop.1', {
        '0.0.2-develop.1': GithubRelease(GHRelease({"tag_name": "0.0.2-develop.1"})),
    }, False),
    ('0.0.2-develop.1', {
        '0.0.2-develop.1': GithubRelease(GHRelease({"tag_name": "0.0.2-develop.1"})),
        '0.0.2-develop.2': GithubRelease(GHRelease({"tag_name": "0.0.2-develop.2"})),
    }, True),
    ('0.0.2-develop.50', {
        '0.0.2-rc.1': GithubRelease(GHRelease({"tag_name": "0.0.2-rc.1"})),
    }, True),
]


class TestUpdater:
    @pytest.mark.parametrize(
        'current,'
        'channel,'
        'candidates,'
        'expected_latest_remote,'
        'expected_new_version_available',
        get_latest_remote)
    def test_get_latest_remote(self,
                               current,
                               channel,
                               candidates,
                               expected_latest_remote,
                               expected_new_version_available,
                               tmpdir):

        p = Path(tmpdir.join('test.exe'))

        upd = Updater(
            executable_name=p.abspath(),
            current_version=current,
            gh_user='132nd-etcher',
            gh_repo='EASI',
            asset_filename='example.zip',
        )

        build_candidates = upd._build_candidates_list
        def make_available_items():
            for k in candidates:
                upd._available[k] = GithubRelease(GHRelease({"tag_name": k}))
            return build_candidates()

        upd._version_check = make_available_items

        upd.channel = channel

        latest_remote, new_version_available = upd._get_latest_remote()
        print(upd._candidates)
        assert latest_remote == expected_latest_remote, latest_remote
        assert new_version_available == expected_new_version_available

    def test_no_release(self, tmpdir):
        p = Path(tmpdir.join('test.exe'))
        upd = Updater(p.abspath(), '0.0.1', '132nd-etcher', 'no_release', 'example.zip')

        with HTTMock(mock_gh_api):
            upd._version_check()
            assert not upd.available

    def test_pre_hook_is_false(self, tmpdir, mocker):
        def pre_hook():
            return False

        cancel_hook = mocker.MagicMock()

        p = Path(tmpdir.join('test.exe'))
        upd = Updater(
            p.abspath(),
            '0.0.1',
            '132nd-etcher',
            'EASI',
            'example.zip',
            pre_update_func=pre_hook,
            cancel_update_func=cancel_hook
        )

        with HTTMock(mock_gh_api):
            upd._version_check()
            assert upd.available
            assert upd._process_candidates() is False
            cancel_hook.assert_called_once_with()

        upd = Updater(
            executable_name=p.abspath(),
            current_version='0.0.1',
            gh_user='132nd-etcher',
            gh_repo='EASI',
            asset_filename='example.zip',
            pre_update_func=pre_hook,
        )

        with HTTMock(mock_gh_api):
            upd._version_check()
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
            upd.channel = channel

    @pytest.mark.parametrize('wrong_param', ['Alpha', '_beta', 'STABLE', 'random', 1, True, None, float(3)])
    def test_wrong_latest_remote(self, tmpdir, wrong_param):
        p = Path(tmpdir.join('test.exe'))
        upd = Updater(p.abspath(), '0.0.1', '132nd-etcher', 'EASI', 'example.zip')
        with pytest.raises(TypeError):
            upd.latest_remote = wrong_param

    @pytest.mark.parametrize('wrong_param', ['Alpha', '_beta', 'STABLE', 'random', 1, True, None, float(3)])
    def test_wrong_latest_candidate(self, tmpdir, wrong_param):
        p = Path(tmpdir.join('test.exe'))
        upd = Updater(p.abspath(), '0.0.1', '132nd-etcher', 'EASI', 'example.zip')
        with pytest.raises(TypeError):
            upd.latest_candidate = wrong_param

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
            upd.channel = channel
            assert upd._version_check() is expected_result
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
            cancel_update_func=cancel,
            auto_update=True
        )

        with HTTMock(mock_gh_api):

            upd.channel = channel

            assert upd._version_check() is expected_result

            upd._process_candidates()

            if expected_result is True:

                pre.assert_called_once_with()
                assert upd._candidates
                assert upd.latest_candidate

                assert isinstance(upd.latest_candidate, GithubRelease)

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

    @pytest.mark.parametrize('current, channel, expected_result', updater_version)
    def test_check_version_no_auto(self, current, channel, expected_result, tmpdir, mocker):

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
            cancel_update_func=cancel,
            auto_update=False
        )

        with HTTMock(mock_gh_api):

            upd.channel = channel

            assert upd._version_check() is expected_result

            upd._process_candidates()

            if expected_result is True:

                pre.assert_called_once_with()
                assert upd._candidates
                assert upd.latest_candidate

                assert isinstance(upd.latest_candidate, GithubRelease)

                class DummyDownloader(Downloader):

                    download_return = True

                    def download(self):
                        self.progress_hooks[0]({'time': '00:00', 'downloaded': 100, 'total': 100})
                        return DummyDownloader.download_return

                mocker.patch('utils.updater.Downloader', new=DummyDownloader)

                upd._download_latest_release()
                assert not upd._update_ready_to_install
                Progress.done()

                DummyDownloader.download_return = False

                upd._download_latest_release()
                cancel.assert_not_called()
                assert not upd._update_ready_to_install
                Progress.done()

            else:

                cancel.assert_called_once_with()

    @pytest.mark.parametrize('local, remote, expected_result', dummy_branches)
    def test_branch_skip(self, tmpdir, local, remote, expected_result):
        p = Path(tmpdir.join('test.exe'))

        upd = Updater(p.abspath(), local, '132nd-etcher', 'EASI', 'example.zip', channel='alpha')

        upd._available = remote

        assert upd._build_candidates_list() is expected_result


