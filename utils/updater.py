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

        if len(self) == 0:
            logger.error('no available release')
            return False

        ret = AvailableReleases()

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

    @staticmethod
    def _download_asset_from_release(gh_release: GithubRelease, asset_filename) -> bool or None:

        def _progress_hook(data):
            label = 'Time left: {} ({}/{})'.format(
                data['time'],
                humanize.naturalsize(data['downloaded']),
                humanize.naturalsize(data['total'])
            )
            Progress.set_label(label)
            Progress.set_value(data['downloaded'] / data['total'] * 100)

        for asset in gh_release.assets:

            logger.debug('checking asset: {}'.format(asset.name))

            if asset.name.lower() == asset_filename.lower():

                Progress.start(
                    title='Downloading latest version',
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

    @staticmethod
    def _install_update(executable: str or Path) -> bool or None:

        if isinstance(executable, str):
            executable = Path(executable)

        if not executable.exists():
            raise FileNotFoundError(executable.abspath())

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


class Updater2:
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
            executable_name: str,
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
        self._executable_name = executable_name
        self._current = Version(current_version)
        self._gh_user = gh_user
        self._gh_repo = gh_repo
        self._channel = None
        self._available = {}
        self._candidates = {}
        self._asset_filename = asset_filename
        self._update_ready_to_install = False
        self.pool = ThreadPool(_num_threads=1, _basename='updater', _daemon=True)

    def _gather_all_available_releases(self):

        self._available = {}

        gh = GHSession()

        logger.debug('querying GH API for available releases')
        releases = gh.get_all_releases(self._gh_user, self._gh_repo)

        if releases:
            logger.debug('found {} available releases on Github'.format(len(releases)))
            for rel in releases:
                self._available[rel.version] = GithubRelease(rel)
                logger.debug('release found: {} ({})'.format(rel.version, self._available[rel.version].channel))

            return len(self._available) > 0

        else:
            logger.error('no release found for "{}/{}"'.format(self._gh_user, self._gh_repo))

    def _filter_releases_by_channel(self, channel: str = 'stable', against: Version = None):

        if channel not in self.valid_channels:
            raise ValueError(channel)

        filtered_releases = {}

        if against is None:
            against = self._current

        min_weight = self.channel_weights[channel]

        if len(self._available) == 0:
            logger.error('no available release')
            return False

        for version_str, release in self._available.items():

            release_version = Version(version_str)

            release_weight = self.channel_weights[release_version.channel]

            if release_weight < min_weight:
                logger.debug('skipping release on channel: {}'.format(release_version.channel))
                continue

            if against.branch is not None and not against.branch == release_version.branch:
                logger.debug('skipping different branch; own: {} remote: {}'.format(
                    against.branch, release_version.branch
                ))
                continue

            filtered_releases[version_str] = release

        return filtered_releases

    def filter_releases_by_versions(self, ):
        pass


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
            executable_name: str,
            current_version: str,
            gh_user: str,
            gh_repo: str,
            asset_filename: str,
            *,
            channel: str = 'stable',
            pre_update_func: callable = None,
            cancel_update_func: callable = None,
            auto_update: bool = False,
            post_check_func: callable = None
    ):
        """
        :param executable_name: local file to update (usually self)
        :param current_version: current running version
        :param gh_user: Github user name
        :param gh_repo: Github repo name
        :param asset_filename: name of the asset in the Github release, usually identical to executable_name
        :param pre_update_func: callable to run before the update; if it returns False, update cancels
        :param cancel_update_func: callable to run in case the update gets cancelled at any point
        """
        self._executable_name = executable_name
        self._current = Version(current_version)
        self._gh_user = gh_user
        self._gh_repo = gh_repo
        self._channel = None
        self._available = {}
        self._candidates = {}
        self._asset_filename = asset_filename
        self._pre_update = pre_update_func
        self._cancel_update_func = cancel_update_func
        self._auto_update = auto_update
        self._post_check_func = post_check_func

        self._update_ready_to_install = False

        self._latest_remote = None
        self._latest_candidate = None

        self.channel = channel

        self.pool = ThreadPool(_num_threads=1, _basename='updater', _daemon=True)

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, value):
        if value not in self.valid_channels:
            raise ValueError('unknown channel: '.format(value))
        self._channel = value

    @property
    def available(self) -> list or None:
        return self._available

    @property
    def latest_candidate(self) -> GithubRelease or None:
        return self._latest_candidate

    @latest_candidate.setter
    def latest_candidate(self, value: GithubRelease):
        if not isinstance(value, GithubRelease):
            raise TypeError('expected GithubRelease instance, got: {}'.format(type(value)))
        self._latest_candidate = value

    @property
    def latest_remote(self) -> Version:
        return self._latest_remote

    @latest_remote.setter
    def latest_remote(self, value: Version):
        if not isinstance(value, Version):
            raise TypeError('expected a Version instance, got: {}'.format(type(value)))
        self._latest_remote = value

    def _version_check(self):

        logger.info('checking for new version on channel: {}'.format(self.channel))

        self._available = {}

        gh = GHSession()

        logger.debug('querying GH API for available releases')
        releases = gh.get_all_releases(self._gh_user, self._gh_repo)

        if releases:
            logger.debug('found {} available releases on Github'.format(len(releases)))
            for rel in releases:
                self._available[rel.version] = GithubRelease(rel)
                logger.debug('release found: {} ({})'.format(rel.version, self._available[rel.version].channel))

        else:
            logger.error('no release found for "{}/{}"'.format(self._gh_user, self._gh_repo))

        return self._build_candidates_list()

    def _build_candidates_list(self):

        min_weight = Updater.channel_weights[self.channel]

        self._candidates = {}

        for version, release in self._available.items():

            version = Version(version)

            if Updater.channel_weights[version.channel] < min_weight:
                logger.debug('skipping release on channel: {}'.format(version.channel))
                continue

            if self._current.branch is not None and not self._current.branch == version.branch:
                logger.debug('skipping different branch; own: {} remote: {}'.format(
                    self._current.branch, version.branch
                ))
                continue

            if self.latest_remote is None or self.latest_remote < version:
                self.latest_remote = version
                logger.debug('latest remote: "{}"'.format(self.latest_remote))

            logger.debug('comparing current with remote: "{}" vs "{}"'.format(self._current, version))
            if version > self._current:
                logger.debug('this version is newer: {}'.format(version))
                self._candidates[version.version_str] = release

        if self.latest_remote:
            logger.debug('latest remote version: {}'.format(self.latest_remote.version_str))

        else:
            logger.warning('no remote version found')

        if self._candidates:
            logger.info('new version found, following up')
            return True

        else:
            logger.info('no new version found')
            return False

    def _process_candidates(self):

        if self._candidates:

            if self._pre_update is not None:

                logger.debug('running pre-update hook')

                if not self._pre_update():

                    logger.debug('pre-update hook returned False, cancelling update')

                    if self._cancel_update_func:
                        self._cancel_update_func()

                    return False

            latest = self._current

            for version, release in self._candidates.items():
                logger.debug('comparing "{}" and "{}"'.format(latest, version))

                version = Version(version)

                if version > self._current:
                    logger.debug('{} is newer'.format(version))
                    latest = version
                    self.latest_candidate = release

            return not latest == self._current

        else:

            logger.debug('no release candidate')

            if self._cancel_update_func:
                self._cancel_update_func()

            return False

    def _download_latest_release(self):

        if not self._auto_update:
            logger.debug('version check done')
            return

        self._update_ready_to_install = False

        def _progress_hook(data):
            label = 'Time left: {} ({}/{})'.format(
                data['time'],
                humanize.naturalsize(data['downloaded']),
                humanize.naturalsize(data['total'])
            )
            Progress.set_label(label)
            Progress.set_value(data['downloaded'] / data['total'] * 100)

        if self.latest_candidate:

            logger.debug('downloading latest release asset')

            asset = self.latest_candidate.get_asset_download_url(self._asset_filename)

            if asset is None:
                logger.error('no asset found with filename: {}'.format(self._asset_filename))

            for asset in self.latest_candidate.assets:

                logger.debug('checking asset: {}'.format(asset.name))

                if asset.name.lower() == self._asset_filename.lower():

                    Progress.start(
                        title='Downloading latest version',
                        length=100,
                        label='')
                    d = Downloader(
                        url=asset.browser_download_url,
                        filename='./update',
                        progress_hooks=[_progress_hook],
                    )
                    if d.download():
                        self._update_ready_to_install = True
                    else:

                        logger.error('download failed')

                        if self._cancel_update_func:
                            self._cancel_update_func()

        else:

            logger.warning('no release to download')

            if self._cancel_update_func:
                self._cancel_update_func()

    def _install_update(self):

        if self._update_ready_to_install:
            logger.debug('installing update')
            # noinspection SpellCheckingInspection
            bat_liiiiiiiiiiiines = [  # I'm deeply sorry ...
                '@echo off',
                'echo Updating to latest version...',
                'ping 127.0.0.1 - n 5 - w 1000 > NUL',
                'move /Y "update" "{}.exe" > NUL'.format(self._executable_name),
                'echo restarting...',
                'start "" "{}.exe"'.format(self._executable_name),
                'DEL update.vbs',
                'DEL "%~f0"',
            ]
            with io.open('update.bat', 'w', encoding='utf-8') as bat:
                bat.write('\n'.join(bat_liiiiiiiiiiiines))

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

        else:

            logger.debug('no update to install')

            if self._cancel_update_func:
                self._cancel_update_func()

    def _version_check_follow_up(self, new_version_found: bool):

        if new_version_found:
            logger.debug('new version found, proceeding')

            self.pool.queue_task(
                task=self._process_candidates,
                _err_callback=self._cancel_update_func,
                _task_callback=self._post_check_func
            )

            self.pool.queue_task(
                task=self._download_latest_release,
                _err_callback=self._cancel_update_func
            )

            self.pool.queue_task(
                task=self._install_update,
                _err_callback=self._cancel_update_func
            )

    def version_check(self):

        self.pool.queue_task(
            task=self._version_check,
            _task_callback=self._version_check_follow_up,
            _err_callback=self._cancel_update_func)

    def _get_latest_remote(self):
        new_version_available = self._version_check()
        return self.latest_remote.version_str if self.latest_remote else None, new_version_available

    def get_latest_remote(self, callback: callable):

        self.pool.queue_task(
            task=self._get_latest_remote,
            _task_callback=callback,
            _err_callback=self._cancel_update_func)

    def _install_latest_remote(self):

        self.pool.queue_task(
            task=self._process_candidates,
            _err_callback=self._cancel_update_func,
            _task_callback=self._post_check_func
        )

        self.pool.queue_task(
            task=self._download_latest_release,
            _err_callback=self._cancel_update_func
        )

        self.pool.queue_task(
            task=self._install_update,
            _err_callback=self._cancel_update_func
        )

    def install_latest_remote(self):

        self.pool.queue_task(
            task=self._install_latest_remote,
            _err_callback=self._cancel_update_func)
