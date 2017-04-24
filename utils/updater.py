# coding=utf-8

import io
import re
import subprocess
from collections import UserDict

import humanize
import semver

from utils.custom_logging import make_logger
from utils.custom_path import Path
from utils.downloader import Downloader
from utils.gh import GHRelease, GHSession
from utils.monkey import nice_exit
from utils.progress import Progress
from utils.threadpool import ThreadPool

logger = make_logger(__name__)


class Version:
    re_branch = re.compile(r'.*\.(?P<branch>.*)\..*?')

    def __init__(self, version_str: str):
        try:
            semver.parse(version_str)
        except ValueError:
            raise ValueError(version_str)
        self._version_str = version_str
        self._channel = None
        self._branch = None

        self._parse()

    def _parse(self):
        info = semver.parse_version_info(self._version_str)
        if info.prerelease is None:
            self._channel = 'stable'
        elif info.prerelease.startswith('alpha.'):
            self._channel = 'alpha'
            self._branch = self.re_branch.match(info.prerelease).group('branch')
        elif info.prerelease.startswith('beta.'):
            self._channel = 'beta'
            self._branch = self.re_branch.match(info.prerelease).group('branch')
        elif info.prerelease.startswith('dev'):
            self._channel = 'dev'
        elif info.prerelease.startswith('rc'):
            self._channel = 'rc'
        else:
            raise ValueError(info.prerelease)

    @property
    def branch(self) -> str or None:
        return self._branch

    @property
    def channel(self) -> str:
        return self._channel

    @property
    def version_str(self):
        return self._version_str

    def __gt__(self, other):
        return semver.compare(self.version_str, other.version_str) > 0

    def __lt__(self, other):
        return semver.compare(self.version_str, other.version_str) < 0

    def __eq__(self, other):
        return semver.compare(self.version_str, other.version_str) == 0

    def __str__(self):
        return self._version_str


class GithubRelease:
    def __init__(self, gh_release: GHRelease):
        self._gh_release = gh_release
        self._version = Version(self._gh_release.version)

    def get_asset_download_url(self, filename):

        logger.debug('found {} assets'.format(self._gh_release.assets_count))

        for asset in self._gh_release.assets:

            logger.debug('eval asset: {}'.format(asset.name))

            if asset.name.lower() == filename.lower():
                logger.debug('asset found, returning download url: {}'.format(asset.browser_download_url))
                return asset.browser_download_url

        logger.warning('no asset found with name: {}'.format(filename))
        return None

    @property
    def version(self):
        return self._version

    @property
    def assets(self):
        return self._gh_release.assets

    @property
    def channel(self) -> str:
        return self._version.channel

    @property
    def branch(self) -> str or None:
        return self._version.branch

    def download_asset(self, asset_filename) -> bool or None:

        def _progress_hook(data):
            label = 'Time left: {} ({}/{})'.format(
                data['time'],
                humanize.naturalsize(data['downloaded']),
                humanize.naturalsize(data['total'])
            )
            Progress.set_label(label)
            Progress.set_value(data['downloaded'] / data['total'] * 100)

        logger.debug('downloading {}'.format(asset_filename))

        for asset in self.assets:

            logger.debug('checking asset: {}'.format(asset.name))

            if asset.name.lower() == asset_filename.lower():

                Progress.start(
                    title='Downloading {} v{}'.format(asset_filename, self.version.version_str),
                    length=100,
                    label='')
                d = Downloader(
                    url=asset.browser_download_url,
                    filename='./update',
                    progress_hooks=[_progress_hook],
                )

                if d.download():
                    return True

        else:

            logger.error('download failed')


class AvailableReleases(UserDict):
    channel_weights = dict(
        alpha=0,
        beta=1,
        dev=2,
        rc=3,
        stable=4
    )

    valid_channels = ['alpha', 'beta', 'dev', 'rc', 'stable']

    def add(self, release: GithubRelease):
        if not isinstance(release, GithubRelease):
            raise TypeError('expected GithubRelease, got: {}'.format(type(release)))
        self.data[release.version.version_str] = release

    def __setitem__(self, *_):
        raise NotImplementedError

    def filter_by_channel(self, channel: str) -> 'AvailableReleases' or None:

        if channel not in self.valid_channels:
            raise ValueError(channel)

        ret = AvailableReleases()

        if len(self) == 0:
            logger.error('no available release')
            return ret

        min_weight = self.channel_weights[channel]

        for version_str, release in self.items():

            release_version = Version(version_str)

            release_weight = self.channel_weights[release_version.channel]

            if release_weight < min_weight:
                logger.debug('skipping release on channel: {}'.format(release_version.channel))
                continue

            ret.add(release)

        return ret

    def filter_by_branch(self, channel: str, branch: str or Version) -> 'AvailableReleases' or None:

        channel_filtered = self.filter_by_channel(channel)

        if not channel_filtered:
            logger.error('no available release on channel: {}'.format(channel))
            return channel_filtered

        if isinstance(branch, Version):
            branch = branch.branch

        ret = AvailableReleases()

        for release in channel_filtered.values():

            if release.branch and not branch == release.branch:
                logger.debug('skipping different branch; own: {} remote: {}'.format(
                    branch, release.branch
                ))
                continue

            ret.add(release)

        return ret

    def get_latest_release(self) -> GithubRelease or None:

        if len(self) == 0:
            logger.error('no release available')
            return

        latest = Version('0.0.0')

        for rel in self.values():
            assert isinstance(rel, GithubRelease)
            if rel.version > latest:
                latest = rel.version

        return self.data[latest.version_str]


class Updater:
    channel_weights = dict(
        alpha=0,
        beta=1,
        dev=2,
        rc=3,
        stable=4
    )

    valid_channels = ['alpha', 'beta', 'dev', 'rc', 'stable']

    def __init__(
            self,
            current_version: str,
            gh_user: str,
            gh_repo: str,
            asset_filename: str,
    ):
        """
        :param executable_name: local file to update (usually self)
        :param current_version: current running version
        :param gh_user: Github user name
        :param gh_repo: Github repo name
        :param asset_filename: name of the asset in the Github release, usually identical to executable_name
        """
        self._current = Version(current_version)
        self._gh_user = gh_user
        self._gh_repo = gh_repo
        self._channel = None
        self._available = AvailableReleases()
        self._asset_filename = asset_filename
        self._update_ready_to_install = False
        self.pool = ThreadPool(_num_threads=1, _basename='updater', _daemon=True)

    def _gather_available_releases(self):

        self._available = AvailableReleases()

        gh = GHSession()

        logger.debug('querying GH API for available releases')
        releases = gh.get_all_releases(self._gh_user, self._gh_repo)

        if releases:
            logger.debug('found {} available releases on Github'.format(len(releases)))
            for rel in releases:
                self._available.add(GithubRelease(rel))
                logger.debug('release found: {} ({})'.format(rel.version, self._available[rel.version].channel))

            return len(self._available) > 0

        else:
            logger.error('no release found for "{}/{}"'.format(self._gh_user, self._gh_repo))

    @staticmethod
    def _install_update(executable: Path) -> bool or None:

        logger.debug('installing update')
        # noinspection SpellCheckingInspection
        bat_liiiiiiiiiiiines = [  # I'm deeply sorry ...
            '@echo off',
            'echo Updating to latest version...',
            'ping 127.0.0.1 - n 5 - w 1000 > NUL',
            'move /Y "update" "{}" > NUL'.format(executable.basename()),
            'echo restarting...',
            'start "" "{}"'.format(executable.basename()),
            'DEL update.vbs',
            'DEL "%~f0"',
        ]
        logger.debug('write bat file')
        with io.open('update.bat', 'w', encoding='utf-8') as bat:
            bat.write('\n'.join(bat_liiiiiiiiiiiines))

        logger.debug('write vbs script')
        with io.open('update.vbs', 'w', encoding='utf-8') as vbs:
            # http://www.howtogeek.com/131597/can-i-run-a-windows-batch-file-without-a-visible-command-prompt/
            vbs.write('CreateObject("Wscript.Shell").Run """" '
                      '& WScript.Arguments(0) & """", 0, False')
        logger.debug('starting update batch file')
        args = ['wscript.exe', 'update.vbs', 'update.bat']
        subprocess.Popen(args)
        # noinspection PyProtectedMember
        # os._exit(0)
        nice_exit(0)

        return True

    def _get_latest_release(self, channel: str = 'stable', branch: str = None):
        self._gather_available_releases()
        return self._available.filter_by_branch(channel, branch).get_latest_release()

    def get_latest_release(
            self,
            channel: str = 'stable',
            branch: str = None,
            success_callback: callable = None,
            failure_callback: callable = None,
    ):
        self.pool.queue_task(
            task=self._get_latest_release,
            kwargs=dict(
                channel=channel,
                branch=branch,
            ),
            _task_callback=success_callback,
            _err_callback=failure_callback
        )

    def _download_and_install_release(
            self,
            release: GithubRelease,
            executable_path: str or Path = None
    ):

        if release.download_asset(self._asset_filename):

            if executable_path is None:

                executable_path = Path(self._asset_filename)

            else:

                if not isinstance(executable_path, Path):
                    executable_path = Path(executable_path)

            if not executable_path.exists():

                logger.error('executable not found: {}'.format(executable_path.abspath()))

            else:

                if self._install_update(executable_path):
                    return True

    def download_and_install_release(
            self,
            release: GithubRelease,
            executable_path: str or Path = None,
            success_callback=None,
            failure_callback=None
    ):
        self.pool.queue_task(
            self._download_and_install_release,
            kwargs=dict(
                release=release,
                executable_path=executable_path,
            ),
            _task_callback=success_callback,
            _err_callback=failure_callback,
        )

    def _find_and_install_latest_release(
            self,
            *,
            channel: str = 'stable',
            branch: str or Version = None,
            cancel_func: callable = None,
            executable_path: str or Path = None
    ):

        self._gather_available_releases()

        if branch is None:
            branch = self._current.branch

        candidates = self._available.filter_by_branch(channel, branch)

        if not candidates:
            logger.info('no new version found')

        else:

            latest_rel = candidates.get_latest_release()

            if latest_rel:  # pragma: no branch

                assert isinstance(latest_rel, GithubRelease)

                logger.debug('latest available release: {}'.format(latest_rel.version))

                if latest_rel.version > self._current:

                    logger.debug('this is a newer version, updating')

                    if self._download_and_install_release(latest_rel, executable_path):
                        return True

        if cancel_func:
            logger.debug('calling cancel callback')
            cancel_func()

    def find_and_install_latest_release(
            self,
            *,
            channel: str = 'stable',
            branch: str or Version = None,
            cancel_func: callable = None,
            failure_callback: callable = None,
            success_callback: callable = None,
            executable_path: str or Path = None
    ):
        self.pool.queue_task(
            self._find_and_install_latest_release,
            kwargs=dict(
                channel=channel,
                branch=branch,
                cancel_func=cancel_func,
                executable_path=executable_path,
            ),
            _task_callback=success_callback,
            _err_callback=failure_callback,
        )
