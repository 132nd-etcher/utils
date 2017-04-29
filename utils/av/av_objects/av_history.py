# coding=utf-8

from utils.custom_session import JSONObject
from .av_project import AVProject
from .av_build import AVAllBuilds


class AVHistory(JSONObject):
    @property
    def project(self):
        return AVProject(self.json['project'])

    @property
    def builds(self):
        return AVAllBuilds(self.json['builds'])