# coding=utf-8

import io
import subprocess
import re

import humanize
import semver

from utils.custom_logging import make_logger
from utils.downloader import Downloader
from utils.gh import GHRelease, GHSession as GH
from utils.progress import Progress
from utils.threadpool import ThreadPool
from utils.monkey import nice_exit

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
            pre_update_func: callable = None,
            cancel_update_func: callable = None,
            auto_update: bool = False
    ):
        """
        :param executable_name: local file to update (usually self)
        :param current_version: current running version
        :param gh_user: Github user name
        :param gh_repo: Github repo name
        :param asset_filename: name of the asset in the Github release, susually identical to executable_name
        :param pre_update_func: callable to run before the update; if it returns False, update cancels
        :param cancel_update_func: callable to run in case the update gets cancelled at any point
        """
        self._executable_name = executable_name
        self._current = Version(current_version)
        self._gh_user = gh_user
        self._gh_repo = gh_repo
        self._available = {}
        self._candidates = {}
        self._latest_release = None
        self._asset_filename = asset_filename
        self._pre_update = pre_update_func
        self._cancel_update_func = cancel_update_func
        self._auto_update = auto_update

        self._update_ready_to_install = False

        self.pool = ThreadPool(_num_threads=1, _basename='updater', _daemon=True)

    def _get_available_releases(self):

        self._available = {}

        gh = GH()

        logger.debug('querying GH API for available releases')
        releases = gh.get_all_releases(self._gh_user, self._gh_repo)

        if releases:
            for rel in releases:
                self._available[rel.version] = GithubRelease(rel)
                logger.debug('release found: {} ({})'.format(rel.version, self._available[rel.version].channel))

        else:
            logger.error('no release found for "{}/{}"'.format(self._gh_user, self._gh_repo))

    @property
    def available(self) -> list or None:
        return self._available

    @property
    def latest_release(self) -> GithubRelease or None:
        return self._latest_release

    def _version_check(self, channel: str = 'stable'):

        if channel not in Updater.valid_channels:
            raise ValueError(channel)

        logger.info('checking for new version on channel: {}'.format(channel))

        self._get_available_releases()

        return self._build_candidates_list(channel)

    def _build_candidates_list(self, channel):

        min_weight = Updater.channel_weights[channel]

        self._candidates = {}

        for version, release in self._available.items():

            version = Version(version)

            if Updater.channel_weights[version.channel] < min_weight:
                logger.debug('skipping release on channel: {}'.format(version.channel))
                continue

            logger.debug('comparing current with remote: "{}" vs "{}"'.format(self._current, version))

            if self._current.branch is not None and not self._current.branch == version.branch:
                logger.debug('skipping different alpha branch; own: {} remote: {}'.format(
                    self._current.branch, version.branch
                ))
                continue

            if version > self._current:
                logger.debug('this version is newer: {}'.format(version))
                self._candidates[version.version_str] = release

        if self._candidates:

            logger.debug('new version found, following up')
            return True

        else:

            logger.debug('no new version found')
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
                    self._latest_release = release

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

        if self._latest_release:

            logger.debug('downloading latest release asset')

            assert isinstance(self._latest_release, GithubRelease)
            asset = self._latest_release.get_asset_download_url(self._asset_filename)

            if asset is None:
                logger.error('no asset found with filename: {}'.format(self._asset_filename))

            assets = self._latest_release.assets

            for asset in assets:

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
                _err_callback=self._cancel_update_func
            )

            self.pool.queue_task(
                task=self._download_latest_release,
                _err_callback=self._cancel_update_func
            )

            self.pool.queue_task(
                task=self._install_update,
                _err_callback=self._cancel_update_func
            )

    def version_check(self, channel: str):

        self.pool.queue_task(
            task=self._version_check,
            kwargs=dict(
                channel=channel
            ),
            _task_callback=self._version_check_follow_up,
            _err_callback=self._cancel_update_func)
