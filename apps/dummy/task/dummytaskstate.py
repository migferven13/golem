import os
import tempfile
from copy import deepcopy

from apps.core.task.coretaskstate import (CoreTaskDefinition,
                                          CoreTaskDefaults)
from apps.dummy.dummyenvironment import DummyTaskEnvironment
from golem.core.common import get_golem_path
from golem.task.taskbasestate import Options


# TODO move it somewhere, but idk where
def ls_R(dir):
    files = []
    for dirpath, dirnames, filenames in os.walk(dir, followlinks=True):
        for name in filenames:
            files.append(os.path.join(dirpath, name))
    return files


class DummyTaskDefaults(CoreTaskDefaults):
    """ Suggested default values for dummy task"""

    def __init__(self):
        super(DummyTaskDefaults, self).__init__()
        self.options = DummyTaskOptions()
        self.options.subtask_data_size = 2048
        self.options.result_size = 256
        self.options.difficulty = 10  # magic number

        self.shared_data_files = ["in.data"]
        self.out_file_basename = "out"
        self.default_subtasks = 5
        self.code_dir = "code_dir"
        self.result_size = 256  # size of subtask result in bytes

        @property
        def full_task_timeout(self):
            return self.default_subtasks * self.subtask_timeout

        @property
        def subtask_timeout(self):
            return 1200


class DummyTaskDefinition(CoreTaskDefinition):
    def __init__(self, defaults=None):
        CoreTaskDefinition.__init__(self)

        self.options = DummyTaskOptions()
        # subtask data
        self.shared_data_files = []

        # subtask code_dir
        self.code_dir = os.path.join(get_golem_path(), "apps", "dummy", "resources", "code_dir")
        self.code_files = []

        self.result_size = 256  # size of subtask result in bytes
        self.out_file_basename = "out"

        if defaults:
            self.set_defaults(defaults)

    def add_to_resources(self):
        super().add_to_resources()
        self.shared_data_files = list(self.resources)

        self.code_files = ls_R(self.code_dir)

        self.tmp_dir = tempfile.mkdtemp()
        os.symlink(self.code_dir, os.path.join(self.tmp_dir, "code"))

        # common_data_path = os.path.commonpath(self.shared_data_files) # makes sense when len(..) > 1
        common_data_path = os.path.dirname(list(self.shared_data_files)[0]) # but we only have 1 file here
        os.symlink(common_data_path, os.path.join(self.tmp_dir, "data"))

        self.resources = set(ls_R(self.tmp_dir))

    # TODO maybe move it to the CoreTask?
    def set_defaults(self, defaults):
        self.shared_data_files = deepcopy(defaults.shared_data_files)
        self.out_file_basename = defaults.out_file_basename
        self.code_dir = defaults.code_dir
        self.result_size = defaults.result_size
        self.total_subtasks = defaults.default_subtasks
        self.options = deepcopy(defaults.options)


class DummyTaskOptions(Options):
    def __init__(self):
        super(DummyTaskOptions, self).__init__()
        self.environment = DummyTaskEnvironment()
        self.subtask_data_size = 128  # size of subtask-specific data in bytes

        # The difficulty is a 4 byte int; 0xffffffff = 32 is the greatest and 0x00000000 = 0
        # the least difficulty. For example difficulty 0x003fffff = (32 - 10) requires
        # 0xffffffff / 0x003fffff = 1024 hash computations on average.
        self.difficulty = 10  # 32 - log2(0x003fffff)
