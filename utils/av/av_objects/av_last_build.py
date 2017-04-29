# coding=utf-8

from utils.custom_session import JSONObject
from .av_project import AVProject
from .av_build import AVBuild


class AVLastBuild(JSONObject):
    @property
    def project(self):
        return AVProject(self.json['project'])

    @property
    def build(self):
        return AVBuild(self.json['build'])