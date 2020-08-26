"""
Helper module that contains monkey patches to embed instance of :class:`ExternalTargetManager`
into mbed os tools.
"""
import atexit
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import traceback
from contextlib import suppress, contextmanager
from functools import wraps
from typing import List, Optional
from unittest.mock import patch

from mbed_host_tests.mbedhtrun import main as htrun_main
from mbed_os_tools.detect.lstools_base import MbedLsToolsBase
from mbed_os_tools.test.host_tests_plugins import HOST_TEST_PLUGIN_REGISTRY as MBED_HOST_TEST_PLUGIN_REGISTRY
from mbed_os_tools.test.host_tests_plugins.host_test_plugins import HostTestPluginBase
from mbed_os_tools.test.mbed_greentea_log import gt_logger
from mbed_os_tools.test.mbed_target_info import TARGET_INFO_MAPPING as MBED_TARGET_INFO_MAPPING
from vznncv.mbed.greentea._external_target_manager import ExternalTargetManager
from vznncv.mbed.greentea._utils import patch_argv, chain_patches, inject_callback_into_output_file_descriptors, \
    FDRedirectionTextLineCallback

logger = logging.getLogger(__name__)


class AugmentedMbedLsToolsBase(MbedLsToolsBase):
    """
    Wrapper around :class:`MbedLsToolsBase` class that adds results of an external script to search results.
    """

    def __init__(self, *, original_instance: MbedLsToolsBase, external_target_manager: ExternalTargetManager, **kwargs):
        super().__init__(**kwargs)
        self._original_instance = original_instance
        self._external_target_manager = external_target_manager

    _cleanup_flag = False
    _tmp_dirs = set()

    @classmethod
    def _cleanup_tmp_dirs(cls):
        for tmp_dir in cls._tmp_dirs:
            shutil.rmtree(tmp_dir)
        cls._tmp_dirs.clear()

    _TARGET_DIR_PREFIX = 'tmp_target_dir_'

    @classmethod
    def _create_dummy_disk_dir(cls, target_id):
        """
        Helper function to create "dummy" target disk directories,
        as internal mbed os tools APIs require it.

        :param target_id:
        :return:
        """
        disk_dir = os.path.abspath(os.path.join(tempfile.gettempdir(), f'{cls._TARGET_DIR_PREFIX}{target_id}'))
        os.makedirs(disk_dir, exist_ok=True)
        cls._tmp_dirs.add(disk_dir)
        if not cls._cleanup_flag:
            atexit.register(cls._cleanup_tmp_dirs)
            cls._cleanup_flag = True
        return disk_dir

    @classmethod
    def disk_name_to_target_id(cls, disk_name):
        """
        Get target id by dummy disk path.

        :param disk_name: disk path
        :return: target_id if it corresponds id that is returned by external script, otherwise ``None``
        """
        disk_name = os.path.basename(disk_name)
        if disk_name.startswith(cls._TARGET_DIR_PREFIX):
            return disk_name[len(cls._TARGET_DIR_PREFIX):]
        else:
            return None

    def find_candidates(self):
        candidates = []
        target_infos = self._external_target_manager.list_targets()

        for target_info in target_infos:
            target_id = target_info['target_id']
            platform_id = target_id[0:4]
            platform_name = target_info['target_name']

            # add found candidate to "Copy/Reset" database
            platform_properties = {
                "copy_method": ExternalTargetManager.COPY_METHOD_NAME
            }
            if target_info['reset_command']:
                platform_properties["reset_method"] = ExternalTargetManager.RESET_METHOD_NAME
            MBED_TARGET_INFO_MAPPING[platform_name] = {"properties": platform_properties}
            # add found candidate to database with platform names
            self.plat_db.add(
                id=platform_id,
                platform_name=platform_name
            )
            # create candidate entity
            candidates.append({
                'target_id_usb_id': target_id,
                'mount_point': self._create_dummy_disk_dir(target_id),
                'serial_port': target_info['serial_port']
            })

        # add candidates from original instance
        candidates.extend(self._original_instance.find_candidates())
        return candidates


def build_mbed_os_detect_tools_patches(external_target_manager: ExternalTargetManager) -> List:
    """
    Patch internal API that detects board.

    :param external_target_manager:
    :return:
    """
    from mbed_os_tools.detect import create as original_create

    @wraps(original_create)
    def patched_create(**kwargs):
        return AugmentedMbedLsToolsBase(
            original_instance=original_create(**kwargs),
            external_target_manager=external_target_manager,
            **kwargs
        )

    return [
        patch.dict(MBED_TARGET_INFO_MAPPING),
        patch('mbed_os_tools.detect.create', new=patched_create)
    ]


class _ProcessLikeThread(threading.Thread):
    """
    Helper wrapper around ``Thread`` to add interface compatibility with a ``Process`` class.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exitcode = None

    def run(self):
        try:
            result = super().run()
        except Exception:
            self.exitcode = 1
            raise
        else:
            self.exitcode = 0
            return result

    def terminate(self):
        pass


_HTRUN_FAILURE_LINE = re.compile(r'\[RXD\] (:\d+::FAIL: .*)')


class _HTRunOutputCallback(FDRedirectionTextLineCallback):
    def __init__(self, output_fileno, output_lines, verbose, **kwargs):
        super().__init__(**kwargs)
        self._output_fileno = output_fileno
        self._output_lines = output_lines
        self._verbose = verbose

    def consume_line(self, original_fd, line: str) -> None:
        output = self.get_sink(self._output_fileno)
        self._output_lines.append(line)
        # process and log htrun output
        test_error = _HTRUN_FAILURE_LINE.search(line)
        if test_error:
            output.write(gt_logger.gt_log_err(test_error.group(1), print_text=False) + '\n')
        if self._verbose:
            output.write(line.rstrip() + '\n')
        output.flush()


def build_htrun_startup_patches(external_target_manager: ExternalTargetManager) -> List:
    """
    Build patches that forces to run htrun in the current process, instead of a new one.

    It allows to apply some patches to htrun, as this tool is responsible.

    :param external_target_manager:
    :return:
    """
    from mbed_os_tools.test.mbed_test_api import run_htrun

    @wraps(run_htrun)
    def patched_run_htrun(cmd, verbose):
        output_lines = []
        stdout_fileno = sys.stdout.fileno()
        stderr_fileno = sys.stderr.fileno()
        output_callback = _HTRunOutputCallback(stdout_fileno, output_lines, verbose)

        with patch_argv(cmd), \
             inject_callback_into_output_file_descriptors([stdout_fileno, stderr_fileno], callback=output_callback):
            ret_code = htrun_main()

        return ret_code, '\n'.join(output_lines)

    return [
        patch('mbed_os_tools.test.mbed_test_api.run_htrun', new=patched_run_htrun),
        patch('mbed_greentea.mbed_test_api.run_htrun', new=patched_run_htrun),
        patch('mbed_os_tools.test.host_tests_runner.host_test_default.Process', new=_ProcessLikeThread)
    ]


class _HTRunLoggerPatch:
    LOGGER_LEVEL = logging.DEBUG
    LOGGER_FORMAT = '[%(created).2f][%(name)s]%(message)s'
    LOGGER_STREAM = sys.stdout
    LOGGER_PROPAGATE = False

    def __init__(self, name):
        self._logger: logging.Logger = logging.getLogger(name)
        self._original_propagate = None
        self._original_level = None
        self._tmp_handler = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        if self._tmp_handler is not None:
            raise ValueError("Patch is already activated")

        self._tmp_handler = logging.StreamHandler(stream=self.LOGGER_STREAM)
        self._tmp_handler.setFormatter(logging.Formatter(fmt=self.LOGGER_FORMAT))
        self._original_propagate = self._logger.propagate
        self._original_level = self._logger.level

        self._logger.propagate = self.LOGGER_PROPAGATE
        self._logger.setLevel(self.LOGGER_LEVEL)
        self._logger.addHandler(self._tmp_handler)

        # clear logger cache
        with suppress(Exception):
            self._logger._cache.clear()

    def stop(self):
        if self._tmp_handler is None:
            raise ValueError("Patch wasn't already activated before")

        self._logger.setLevel(self._original_level)
        self._logger.propagate = self._original_propagate
        self._logger.removeHandler(self._tmp_handler)

        # clear logger cache
        with suppress(Exception):
            self._logger._cache.clear()

        self._tmp_handler = None


_HTRUN_LOGGER_NAMES = ['HTST', 'CONN', 'PLGN', 'COPY', 'REST', 'MBED']


def build_htrun_logger_patches(external_target_manager: ExternalTargetManager) -> List:
    """
    Patch htrun logger for a correct output.

    :param external_target_manager:
    :return:
    """
    return [_HTRunLoggerPatch(name) for name in _HTRUN_LOGGER_NAMES]


class _ExternalScriptBasePlugin(HostTestPluginBase):
    def __init__(self, external_target_manager: ExternalTargetManager):
        super().__init__()
        self.external_target_manager: ExternalTargetManager = external_target_manager

    def setup(self, *args, **kwargs):
        return True

    def _resolve_target_id(self, kwargs):
        # resolve target id
        target_id = kwargs.get('target_id')
        if target_id is None:
            # try to extract target id from disk path
            destination_disk = kwargs.get('destination_disk')
            if destination_disk is None:
                raise ValueError(f"Cannot resolve target_id from as \"target_id\" or \"destination_disk\" aren't set")
            target_id = AugmentedMbedLsToolsBase.disk_name_to_target_id(destination_disk)
            if target_id is None:
                raise ValueError(f"Cannot resolve target_id from destination disk: {destination_disk}")
        return target_id


class _ExternalScriptCopyMethod(_ExternalScriptBasePlugin):
    name = 'ExternalScriptCopyMethod'
    type = 'CopyMethod'
    stable = True
    capabilities = [ExternalTargetManager.COPY_METHOD_NAME]
    required_parameters = ['image_path']

    def execute(self, capability, *args, **kwargs):
        if not self.check_parameters(capability, *args, **kwargs):
            raise ValueError("Invalid plugin parameters. See logs")

        target_id = self._resolve_target_id(kwargs)
        image_path = kwargs['image_path']

        cmd_result = True
        try:
            self.external_target_manager.flash_target(target_id=target_id, image_path=image_path)
        except Exception:
            logger.info(f"Fail to flush image \"{image_path}\" to target {target_id}\n{traceback.format_exc()}")
            cmd_result = False
        return cmd_result


class _ExternalScriptResetMethod(_ExternalScriptBasePlugin):
    name = 'ExternalScriptResetMethod'
    type = 'ResetMethod'
    stable = True
    capabilities = [ExternalTargetManager.RESET_METHOD_NAME]
    required_parameters = []

    def execute(self, capability, *args, **kwargs):
        if not self.check_parameters(capability, *args, **kwargs):
            raise ValueError("Invalid plugin parameters. See logs")

        target_id = self._resolve_target_id(kwargs)

        cmd_result = True
        try:
            self.external_target_manager.reset_target(target_id=target_id)
        except Exception:
            logger.info(f"Fail to reset target {target_id}\n{traceback.format_exc()}")
            cmd_result = False
        return cmd_result


class _PatchHtrunPlugins:
    def __init__(self, external_target_manager: ExternalTargetManager):
        self._external_target_manager = external_target_manager

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        MBED_HOST_TEST_PLUGIN_REGISTRY.register_plugin(_ExternalScriptCopyMethod(self._external_target_manager))
        MBED_HOST_TEST_PLUGIN_REGISTRY.register_plugin(_ExternalScriptResetMethod(self._external_target_manager))

    def stop(self):
        MBED_HOST_TEST_PLUGIN_REGISTRY.PLUGINS.pop(_ExternalScriptCopyMethod.name, None)
        MBED_HOST_TEST_PLUGIN_REGISTRY.PLUGINS.pop(_ExternalScriptResetMethod.name, None)


def build_htrun_plugin_patches(external_target_manager: ExternalTargetManager) -> List:
    """
    Build patches that adds htrun plugins that allows to upload firwmare and reset board with custom script.

    :param external_target_manager:
    :return:
    """
    return [_PatchHtrunPlugins(external_target_manager)]


_BOARD_MANAGER_SCRIPT_PATCH_BUILDERS = [
    build_htrun_logger_patches,
    build_mbed_os_detect_tools_patches,
    build_htrun_startup_patches,
    build_htrun_plugin_patches
]


def build_mbed_api_patches_for_external_target_script(external_target_manager: ExternalTargetManager):
    """
    Build Mbed Greenea patches that embeds :class:`ExternalTargetManager` into Greentea workflow.

    :param external_target_manager:
    :return:
    """
    api_patches = []
    for patch_builder in _BOARD_MANAGER_SCRIPT_PATCH_BUILDERS:
        api_patches.extend(patch_builder(external_target_manager))
    return api_patches


@contextmanager
def apply_mbed_api_patches_for_external_target_script(external_target_manager: Optional[ExternalTargetManager]):
    """
    Context manager to apply patches from :func:`build_mbed_api_patches`.

    If ``external_target_manager`` is ``None``, then no patches are applied.

    :param external_target_manager:
    :return:
    """
    if external_target_manager is not None:
        api_patches = build_mbed_api_patches_for_external_target_script(external_target_manager)
    else:
        api_patches = []

    with chain_patches(api_patches):
        yield
