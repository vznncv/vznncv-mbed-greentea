import logging
import os.path
import subprocess
from contextlib import contextmanager
from typing import Dict, Optional

import vznncv.mbed.greentea._mbed_cli  as mbed_cli_executor
from ._program_cfg import ProgramConfig

logger = logging.getLogger(__name__)


@contextmanager
def patch_mbedignore_for_greentea_tests(project_dir):
    """
    Patch .mbedignore to skip main.cpp or src/main.cpp

    :param project_dir: project directory
    """
    mbedignore_path = os.path.join(project_dir, '.mbedignore')

    # read original .mbedignore content
    if os.path.exists(mbedignore_path):
        with open(mbedignore_path, encoding='utf-8') as f:
            original_data = f.read()
        # cleanup original data if previous run failed
        res_lines = []
        for line in original_data.splitlines(True):
            if line.startswith("# GREENTEA_COMPILE_PROJECT_PATH"):
                break
            res_lines.append(line)
        original_data = ''.join(res_lines)

    else:
        original_data = None

    # append path
    with open(mbedignore_path, 'a', encoding='utf-8') as f:
        f.write('# GREENTEA_COMPILE_PROJECT_PATH START\n')
        # ignore typical main file locations
        # root folder
        f.write('main.cpp\n')
        f.write('*_main.cpp\n')
        # project suborders like "src", "source", etc.
        f.write('*/main.cpp\n')
        f.write('*/*_main.cpp\n')
        f.write('# GREENTEA_COMPILE_PROJECT_PATH END\n')

    try:
        yield
    finally:
        # restore original .mbedignore
        if original_data is None:
            os.remove(mbedignore_path)
        else:
            with open(mbedignore_path, 'w', encoding='utf-8') as f:
                f.write(original_data)


def build_tests(project_dir, *, tests_by_name=None, app_config=None, profile=None, verbose_level=0):
    """
    Helper wrapper around mbed tools to compile green-tea tests.

    :param project_dir:
    :param tests_by_name:
    :param app_config:
    :param profile:
    :param verbose_level:
    :return:
    """
    program_config = ProgramConfig(project_dir)
    profile = program_config.resolve_profile(profile)

    mbed_cli_args = ['test', '--greentea', '--compile', '--profile', profile]
    if tests_by_name is not None:
        mbed_cli_args.extend(['--tests-by-name', tests_by_name])
    if app_config is not None:
        mbed_cli_args.extend(['--app-config', app_config])
    if verbose_level > 0:
        mbed_cli_args.append('-' + 'v' * verbose_level)

    with patch_mbedignore_for_greentea_tests(project_dir):
        try:
            mbed_cli_executor.run_mbed_cli_command(mbed_cli_args, project_dir=project_dir, check=True)
        except subprocess.CalledProcessError as e:
            raise ValueError("Fail to compile greentea tests") from e


_ARTIFACT_EXTENSIONS = [
    'elf',
    'bin',
    'hex'
]


def build_main(project_dir, *, app_config=None, profile=None, verbose_level=0, no_compile=False) -> Dict[
    str, Optional[str]]:
    """
    Helper wrapper to build project.

    The function returns paths to build artifacts.

    :param project_dir:
    :param tests_by_name:
    :param app_config:
    :param profile:
    :param verbose_level:
    :param no_compile: don't build artifact and simply return path to existed ones
    :return:
    """
    program_config = ProgramConfig(project_dir)
    profile = program_config.resolve_profile(profile)
    profile_name = os.path.splitext(os.path.basename(profile))[0]
    target_name = program_config.resolve_target()
    toolchain_name = program_config.resolve_toolchaing()

    if not no_compile:
        mbed_cli_args = ['compile', '--profile', profile]
        if verbose_level > 0:
            mbed_cli_args.append('-' + 'v' * verbose_level)
        if app_config:
            mbed_cli_args.extend(['--app-config', app_config])
        mbed_cli_executor.run_mbed_cli_command(mbed_cli_args, project_dir=project_dir, check=True)

    # search build artifacts
    artifact_dir_path = os.path.join(program_config.get_build_dir(), target_name.upper(),
                                     toolchain_name.upper() + '-' + profile_name.upper())
    if not os.path.isdir(artifact_dir_path):
        raise ValueError(f"Build directory \"{artifact_dir_path}\" doesn't exist")

    result = {}
    artifact_name = program_config.program_name
    for artifact_ext in _ARTIFACT_EXTENSIONS:
        artifact_path = os.path.abspath(os.path.join(artifact_dir_path, f'{artifact_name}.{artifact_ext}'))
        if os.path.isfile(artifact_path):
            result[artifact_ext] = artifact_path
    if not result:
        raise ValueError("Cannot find any build artifact after compilation in the folder \"{artifact_dir_path}\"")

    return result
