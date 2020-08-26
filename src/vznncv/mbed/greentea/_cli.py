import logging
import os
import sys

import click

logger = logging.getLogger(__name__)

##
# Common click "options" for some subcommands
##

_click_option_project_dir = click.option(
    '--project-dir', default=lambda: os.getcwd(),
    help='Project director'
)
_click_option_board_manager_script = click.option(
    '-s', '--board-manager-script',
    help='Custom script that detect targets and upload firmware'
)
_click_option_no_compile = click.option(
    '--no-compile', is_flag=True,
    help='Try to run tests using existed compiled images'
)
_click_option_profile = click.option(
    '--profile',
    help='Path to build profile or predefined profile name. '
         'Use `mbed config PROFILE <profile_name>` to set default project profile'
)
_click_option_verbose_level = click.option(
    '-v', '--verbose', 'verbose_level', count=True,
    help="Verbose output"
)
_ENVVAR_PARAM_PREFIX = 'VZNNCV_MBEDGTW'


def _log_app_envvar(verbose_level: int):
    if verbose_level <= 0:
        return
    full_env_prefix = f'{_ENVVAR_PARAM_PREFIX}_'
    app_env_vars = {k: v for k, v in os.environ.items() if k.startswith(full_env_prefix)}
    logger.info("Application control environment variables:")
    for key in sorted(app_env_vars):
        logger.info(f"- {key}: {app_env_vars[key]}")


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')


@main.command(context_settings=dict(auto_envvar_prefix=_ENVVAR_PARAM_PREFIX))
@_click_option_project_dir
@_click_option_verbose_level
def list_tests(project_dir, verbose_level):
    """
    List available tests that can be compiled and run.
    """
    _log_app_envvar(verbose_level)
    import vznncv.mbed.greentea._mbed_cli as mbed_cli_executor
    mbed_cli_executor.run_mbed_cli_command(['test', '--greentea', '--compile-list'], project_dir=project_dir,
                                           check=True)


@main.command(context_settings=dict(auto_envvar_prefix=_ENVVAR_PARAM_PREFIX))
@_click_option_board_manager_script
@_click_option_verbose_level
@click.option('-j', '--json', 'json_flag', is_flag=True, help='Print json object instead of table')
def list_targets(board_manager_script, json_flag, verbose_level):
    """
    List available targets.
    """
    _log_app_envvar(verbose_level)
    import json
    from vznncv.mbed.greentea._test_runner import list_targets
    from mbed_os_tools.test.mbed_test_api import log_mbed_devices_in_table

    targets = list_targets(board_manager_script)

    if json_flag:
        print(json.dumps(targets, indent=4))
    else:
        print(log_mbed_devices_in_table(targets))


@main.command(context_settings=dict(auto_envvar_prefix=_ENVVAR_PARAM_PREFIX))
@_click_option_project_dir
@_click_option_verbose_level
@click.option('-n', '--tests-by-name', help='Limit the tests to a list (ex. test1,test2,test3)')
@_click_option_profile
@_click_option_board_manager_script
@_click_option_no_compile
def run_tests(project_dir, verbose_level, tests_by_name, profile, board_manager_script, no_compile):
    """
    Compile and run greentea tests.
    """
    _log_app_envvar(verbose_level)
    from vznncv.mbed.greentea._test_builder import build_tests
    from vznncv.mbed.greentea._test_runner import run_tests

    if not no_compile:
        logger.info("Build tests ...")
        ret_code = build_tests(
            project_dir=project_dir,
            tests_by_name=tests_by_name,
            profile=profile,
            verbose_level=verbose_level
        )
        if ret_code:
            logger.error("Fail to build tests")
            sys.exit(ret_code)
    logger.info("Run tests")
    ret_code = run_tests(
        project_dir=project_dir,
        board_manager_script=board_manager_script,
        tests_by_name=tests_by_name,
        verbose_level=verbose_level
    )
    if ret_code:
        logger.error("Some tests have failed")
        sys.exit(ret_code)
    logger.info("Complete")


@main.command(context_settings=dict(auto_envvar_prefix=_ENVVAR_PARAM_PREFIX))
@_click_option_project_dir
@_click_option_verbose_level
@_click_option_profile
@_click_option_board_manager_script
@_click_option_no_compile
def run_main(project_dir, verbose_level, profile, board_manager_script, no_compile):
    """
    Run current project as a greentea test.

    It can be useful to write your test with IDE in main.cpp of a program.
    """
    _log_app_envvar(verbose_level)
    from vznncv.mbed.greentea._test_builder import build_main
    from vznncv.mbed.greentea._test_runner import flash_artifact, debug_test

    build_artifacts = build_main(
        project_dir=project_dir,
        profile=profile,
        verbose_level=verbose_level,
        no_compile=no_compile
    )

    # select binary artifact or any available one
    artifact_path = build_artifacts.pop('bin', None)
    if artifact_path is None and build_artifacts:
        artifact_path = next(iter(build_artifacts.values()))
    if not artifact_path:
        raise ValueError("No build artifacts are created")

    # flush firmware
    flash_artifact(
        project_dir=project_dir,
        board_manager_script=board_manager_script,
        verbose_level=verbose_level,
        artifact_path=artifact_path
    )
    # run test
    ret_code = debug_test(
        project_dir=project_dir,
        board_manager_script=board_manager_script,
        verbose_level=verbose_level
    )
    if ret_code:
        logger.error("Some tests have failed")
        sys.exit(ret_code)
    logger.info("Complete")


@main.command(context_settings=dict(auto_envvar_prefix=_ENVVAR_PARAM_PREFIX))
@_click_option_project_dir
@_click_option_board_manager_script
@_click_option_verbose_level
def debug_test(project_dir, board_manager_script, verbose_level):
    """
    Run tests without compilation, flushing and target resetting for debugging purposes.
    """
    _log_app_envvar(verbose_level)
    from vznncv.mbed.greentea._test_runner import debug_test
    ret_code = debug_test(
        project_dir=project_dir,
        board_manager_script=board_manager_script,
        verbose_level=verbose_level
    )
    if ret_code:
        logger.error("Some tests have failed")
        sys.exit(ret_code)
    logger.info("Complete")


if __name__ == '__main__':
    main()
