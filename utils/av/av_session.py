# coding=utf-8

import requests
from utils.custom_logging import make_logger
from utils.av.av_objects.av_last_build import AVLastBuild
from utils.av.av_objects.av_history import AVHistory
from utils.av.av_objects.av_artifact import AllAVArtifacts


logger = make_logger(__name__)


class AVSession(requests.Session):

    def __init__(self):

        requests.Session.__init__(self)

        self.base = [r'https://ci.appveyor.com/api']

        self.__resp = None

        self.req = None

    @property
    def resp(self) -> requests.models.Response:
        return self.__resp

    def build_req(self, *args):

        # if not args:
        #     raise ValueError('request is empty')

        for x in args:
            if not isinstance(x, str):
                raise TypeError('expected a string, got: {} ({})'.format(x, args))

        self.req = '/'.join(self.base + list(args))

        return self.req

    def __parse_resp_error(self):

        logger.error(self.req)
        logger.error(self.resp)
        logger.error(self.__resp.reason)

        raise Exception('request failed')

    def __parse_resp(self) -> requests.models.Response:

        if self.__resp is None:
            raise Exception('did not get any response from: {}'.format(self.req))

        if not self.__resp.ok:
            self.__parse_resp_error()

        logger.debug(self.__resp.reason)

        return self.__resp

    def _get(self, **kwargs) -> requests.models.Response:

        logger.debug(self.req)

        self.__resp = super(AVSession, self).get(self.req, **kwargs)

        return self.__parse_resp()

    def _get_json(self, **kwargs) -> requests.models.Response:

        req = self._get(**kwargs)

        return req.json()

    def get_last_build(self, av_user_name, av_project_name, branch: str = None) -> AVLastBuild:

        req_params = ['projects', av_user_name, av_project_name]

        if branch:

            req_params.extend(['branch', branch])

        self.build_req(*req_params)

        return AVLastBuild(self._get_json())

    def get_artifacts(self, job_id):

        self.build_req('buildjobs', job_id, 'artifacts')

        return AllAVArtifacts(self._get_json())

    def get_history(self, av_user_name, av_project_name, build_count=9999) -> AVHistory:
        """
        Gets build history from the top down
        
        :param build_count: max number of builds to retrieve
        :param av_user_name: AV user name 
        :param av_project_name: AV project name
        :return: AVHistory object
        """

        self.build_req('projects', av_user_name, av_project_name, 'history', '?recordsNumber={}'.format(build_count))

        return AVHistory(self._get_json())

    def get_latest_build_on_branch(self, av_user_name, av_project_name, branch) -> AVLastBuild:

        self.build_req('projects', av_user_name, av_project_name, 'branch', branch)

        return AVLastBuild(self._get_json())

    def get_build_by_version(self, av_user_name, av_project_name, build_id) -> AVLastBuild:

        self.build_req('projects', av_user_name, av_project_name, 'build', build_id)

        return AVLastBuild(self._get_json())


if __name__ == '__main__':
    av = AVSession()

    params = ['132nd-etcher', 'EMFT']

    latest = av.get_last_build(*params)
    arti = av.get_artifacts(latest.build.jobs[0].jobId)[0]
    print(arti.size, arti.name, arti.fileName, arti.type)

    print(arti.url_safe_file_name)

    exit(0)

    history = av.get_history('132nd-etcher', 'EMFT')
    # history.builds.print_all()
    for latest in history.builds:
        if not latest.status == 'success':
            logger.info('skipping failed build: {build.buildId} ({build.commitId})'.format(build=latest))
            continue
        try:
            logger.info('found build: {build.buildId} ({build.commitId}) on branch {build.branch}'.format(build=latest))
            latest.print_all()
        except ValueError:
            logger.warning('skipping badly formatted version: {}'.format(latest._full_version_str))
            pass

    # from utils.gh import GHSession
    #
    #
    #
    # rel = GHSession().get_latest_release(*params)
    #
    # asset = rel.assets[0]
    #
    # print(asset.name)

    #
    # branches = GHSession().get_branches()
    #
    # for b in branches:
    #     print(b.name)


    exit(0)
    last_build = av.get_last_build('132nd-etcher', 'EMFT', 'feature/av-updater')
    # last_build = av.get_last_build('132nd-entropy', '132nd-virtual-wing-training-mission-tblisi')
    last_build.print_all()
    # for x in last_build.build.jobs.with_artifacts():
    #     print(av.get_artifacts(x.jobId))
