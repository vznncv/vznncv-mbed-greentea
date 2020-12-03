import logging
from typing import Optional, Dict

from mbed_os_tools.detect.lstools_base import MbedLsToolsBase

import mbed_os_tools.detect
from mbed_greentea import main as mbed_greentea_main
from mbed_host_tests.mbedhtrun import main as htrun_main
from mbed_os_tools.test import mbed_target_info
import mbed_os_tools.test.host_tests_plugins as mbed_host_tests_plugins

from ._external_target_manager import ExternalTargetManager
from ._external_target_manager_patches import apply_mbed_api_patches_for_external_target_script
from ._program_cfg import ProgramConfig, AppConfig
from ._utils import patch_cwd, patch_argv

logger = logging.getLogger(__name__)


##
# Helper functions to build mbed tools patches to embed custom target functionality
##


def list_targets(board_manager_script: Optional[str] = None):
    """
    Helper function to list available targets.

    :param board_manager_script:
    :return:
    """
    external_target_manager = ExternalTargetManager(board_manager_script) if board_manager_script is not None else None

    with apply_mbed_api_patches_for_external_target_script(external_target_manager):
        mbeds = mbed_os_tools.detect.create()
        return mbeds.list_mbeds(unique_names=True, read_details_txt=True)


def run_tests(project_dir, *, board_manager_script: Optional[str] = None, tests_by_name: Optional[str] = None,
              verbose_level: int = 0) -> int:
    """
    Helper functions to run tests.

    The tests should be compiled before function invocation

    :param project_dir:
    :param board_manager_script: helper script with custom firmware uploading functionality
    :param tests_by_name:
    :param verbose_level:
    :return: greentea return code
    """

    greentea_cli_args = ['mbedgt']
    if tests_by_name:
        greentea_cli_args.extend(['--test-by-names', tests_by_name])
    if verbose_level > 0:
        greentea_cli_args.append('--verbose')
        greentea_cli_args.append('--verbose-test-result')

    external_target_manager = ExternalTargetManager(board_manager_script) if board_manager_script is not None else None

    try:
        with apply_mbed_api_patches_for_external_target_script(external_target_manager), \
             patch_cwd(project_dir), patch_argv(greentea_cli_args):
            ret_code = mbed_greentea_main()
    except SystemExit as e:
        ret_code = e.code
    ret_code = ret_code or 0

    if ret_code:
        logger.error(f"greentea has failed with a code {ret_code}")
    return ret_code


def _find_target(mbeds: MbedLsToolsBase, target_name) -> Dict:
    """
    Find specified target.

    :param mbeds:
    :param target_name:
    :return:
    """
    target_mbeds = []
    for mbed_info in mbeds.list_mbeds(unique_names=True, read_details_txt=True):
        if mbed_info['platform_name'] == target_name:
            target_mbeds.append(mbed_info)
    if len(target_mbeds) == 0:
        raise ValueError(f"No \"{target_name}\" boards are found")
    elif len(target_mbeds) > 1:
        raise ValueError(f"Multiple \"{target_name}\" boards are found")
    return target_mbeds[0]


_DEFAULT_BAUDRATE = 9600
_DEFAULT_PROGRAM_CYCLES_S = 4
_DEFAULT_POOLING_TIMEOUT = 60


def flash_artifact(project_dir, *, board_manager_script: Optional[str] = None, verbose_level: int = 0, artifact_path):
    """
    Upload specified artifact to a board.

    :param project_dir:
    :param board_manager_script:
    :param verbose_level:
    :param artifact_path:
    :return:
    """
    program_config = ProgramConfig(project_dir)
    app_config = AppConfig(project_dir)

    # resolve baudrate and platform name
    serial_port_baudrate = app_config.get_parameter('platform.stdio-baud-rate', _DEFAULT_BAUDRATE)
    target_name = program_config.resolve_target()

    external_target_manager = ExternalTargetManager(board_manager_script) if board_manager_script is not None else None

    with apply_mbed_api_patches_for_external_target_script(external_target_manager), patch_cwd(project_dir):
        # find target board
        target_mbed = _find_target(mbed_os_tools.detect.create(), target_name)
        target_id = target_mbed['target_id']
        copy_method = mbed_target_info.get_platform_property(target_mbed['platform_name'], 'copy_method')

        result = mbed_host_tests_plugins.call_plugin(
            'CopyMethod',
            capability=copy_method,
            image_path=artifact_path,
            serial=f"{target_mbed['serial_port']}:{serial_port_baudrate}",
            destination_disk=target_mbed['mount_point'],
            target_id=target_id,
            pooling_timeout=_DEFAULT_POOLING_TIMEOUT
        )
        if not result:
            raise ValueError(f"Fail to upload image to \"{artifact_path}\" to target \"{target_id}\"")

    return 0


def debug_test(project_dir, *, board_manager_script: Optional[str] = None, verbose_level: int = 0):
    """
    Run test without uploading.

    It's useful if you want to debug test inside IDE.

    :param project_dir:
    :param board_manager_script:
    :param verbose_level:
    :return:
    """
    program_config = ProgramConfig(project_dir)
    app_config = AppConfig(project_dir)

    # resolve baudrate and platform name
    serial_port_baudrate = app_config.get_parameter('platform.stdio-baud-rate', _DEFAULT_BAUDRATE)
    target_name = program_config.resolve_target()

    external_target_manager = ExternalTargetManager(board_manager_script) if board_manager_script is not None else None

    with apply_mbed_api_patches_for_external_target_script(external_target_manager), patch_cwd(project_dir):
        # find target board
        target_mbed = _find_target(mbed_os_tools.detect.create(), target_name)
        serial_port = target_mbed['serial_port']
        target_id = target_mbed['target_id']
        reset_method = mbed_target_info.get_platform_property(target_mbed['platform_name'], 'reset_method')

        # run htrun to debut test
        mbedhtrun_args = [
            'mbedhtrun'
            '--micro', 'target_name',
            '--target-id', target_id,
            '--sync', '5',
            '--port', f'{serial_port}:{serial_port_baudrate}',
            '--reset', reset_method,
            '--skip-flashing',
            '--skip-reset',
        ]
        if verbose_level >= 0:
            mbedhtrun_args.append('--verbose')

        with patch_argv(mbedhtrun_args):
            logger.info(f"Run command: {' '.join(mbedhtrun_args)}")
            try:
                ret_code = htrun_main()
            except SystemExit as e:
                ret_code = e.code
            ret_code = ret_code or 0

    if ret_code:
        logger.error(f"mbedhtrun has failed with a code {ret_code}")
    return ret_code
