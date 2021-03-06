from fs import open_fs
from typing import Dict, Set
import inspect
from abc import ABC, abstractmethod
from .fileref import FileRef
from .workarounds.annot import is_fileset
from .exceptions import (
    FileSetError,
    CircularFileSetError,
    BakerError,
    SeriousErrorThatYouShouldOpenAnIssueForIfYouGet,
)
from .context import BakerContext, get_default_context
from .util import get_files_in_path_dict


PathDict = Dict[str, str]
FileDict = Dict[str, FileRef]
TagSet = Set[str]


class Transform(ABC):
    input_tags: TagSet = set()
    output_tags: TagSet = set()

    def __init__(
        self,
        input_paths: PathDict,
        output_paths: PathDict,
        context: BakerContext = get_default_context(),
        overwrite: bool = False,
    ):
        self.input_paths = input_paths
        self.output_paths = output_paths
        self.input_files: FileDict = {}
        self.output_files: FileDict = {}
        self.context = context
        self.overwrite = overwrite
        self._current_run_info = None

    def _init_file_dicts(self, input_paths: PathDict, output_paths: PathDict):
        if set(input_paths) != self.input_tags:
            raise FileSetError(set(input_paths), self.input_tags)

        if set(output_paths) != self.output_tags:
            raise FileSetError(set(output_paths), self.output_tags)

        input_path_set = get_files_in_path_dict(input_paths)
        output_path_set = get_files_in_path_dict(output_paths)
        intersection = set.intersection(input_path_set, output_path_set)
        if len(intersection):
            raise CircularFileSetError(
                "File included as both input and output: {}".format(
                    ", ".join(intersection)
                )
            )

        # TODO: Clean up this fileset code, like a lot
        for tag in input_paths:
            if is_fileset(tag):
                refset = []
                for individual_path in input_paths[tag]:
                    refset.append(
                        FileRef(
                            individual_path,
                            read_bit=True,
                            write_bit=False,
                            run_info=self._current_run_info,
                        )
                    )
                self.input_files[tag] = refset
            else:
                self.input_files[tag] = FileRef(
                    input_paths[tag],
                    read_bit=True,
                    write_bit=False,
                    run_info=self._current_run_info,
                )

        for tag in output_paths:
            if is_fileset(tag):
                refset = []
                for individual_path in output_paths[tag]:
                    refset.append(
                        FileRef(
                            individual_path,
                            read_bit=False,
                            write_bit=True,
                            run_info=self._current_run_info,
                        )
                    )
                self.output_files[tag] = refset
            else:
                self.output_files[tag] = FileRef(
                    output_paths[tag],
                    read_bit=False,
                    write_bit=True,
                    run_info=self._current_run_info,
                )

    def _validate_file_existence(self):
        overwrite = self.overwrite

        def ensure_input_exists(file_ref):
            if not file_ref.exists():
                raise BakerError(
                    "Referenced input path {} does not exist!".format(file_ref.path)
                )

        for tag in self.input_files:
            if is_fileset(tag):
                for path in self.input_files[tag]:
                    ensure_input_exists(path)
            else:
                ensure_input_exists(self.input_files[tag])

        def ensure_output_doesnt_exist(file_ref):
            if (not overwrite) and file_ref.exists():
                raise BakerError(
                    "Referenced output path {} already exists, and overwrite is not enabled".format(
                        file_ref.path
                    )
                )

        for tag in self.output_files:
            if is_fileset(tag):
                for path in self.output_files[tag]:
                    ensure_output_doesnt_exist(path)
            else:
                ensure_output_doesnt_exist(self.output_files[tag])

    def run(self):
        self.context.run_transform(self)

    def _exec_with_run_info(self, run_info):
        self._current_run_info = run_info
        self._init_file_dicts(self.input_paths, self.output_paths)
        self._validate_file_existence()
        if not run_info:
            raise SeriousErrorThatYouShouldOpenAnIssueForIfYouGet(
                "No current run information, somehow!"
            )
        self.script()

    @abstractmethod
    def script(self):
        pass
