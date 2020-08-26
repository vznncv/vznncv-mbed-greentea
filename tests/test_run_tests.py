import json
import os.path
from typing import Callable

import pytest
from hamcrest import assert_that, equal_to, has_items, not_, string_contains_in_order

from testing_utils import VirtualComPortStub, TransparentOutputCliRunner, build_target_test_serial_callback
from vznncv.mbed.greentea._cli import main as main_cli
from vznncv.mbed.greentea._program_cfg import ProgramConfig

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'simple_project')

_TEST_TARGET_NAME = 'BLACKPILL_F401CC'
_TEST_TARGET_ID = 'FFFF00000000000000000000'
_TEST_SERIAL_PORT = '/dev/ttyUSB0'
_TEST_IMAGE_FORAT = 'elf'
_TEST_RESET_METHOD = 'true'
_TEST_TARGET_IS_CONNECTED = '1'
_TEST_SERIAL_SPEED = 9600
_TEST_NAME = 'tests-demo-demo'
_TEST_TARGET_FULL_NAME = f'{_TEST_TARGET_NAME}-GCC_ARM'

_DEFAULT_ENV = {
    'TEST_TARGET_NAME': _TEST_TARGET_NAME,
    'TEST_TARGET_ID': _TEST_TARGET_ID,
    'TEST_SERIAL_PORT': _TEST_SERIAL_PORT,
    'TEST_IMAGE_FORMAT': _TEST_IMAGE_FORAT,
    'TEST_RESET_METHOD': _TEST_RESET_METHOD,
    'TEST_TARGET_IS_CONNECTED': _TEST_TARGET_IS_CONNECTED
}

_BUILD_EXTS = ['bin', 'hex', 'elf']


def _build_dummy_test(project_dir: str, program_config: ProgramConfig, baudrate: int, testname: str):
    # create dummy test director
    project_dir = os.path.abspath(project_dir)
    target = program_config.resolve_target()
    toolchain = program_config.resolve_toolchaing()
    profile = program_config.resolve_profile()

    test_build_dir = os.path.join(
        program_config.get_build_dir(),
        'tests',
        target.upper(),
        toolchain.upper() + '-' + profile.upper()
    )
    base_test_build_dir = os.path.relpath(test_build_dir, project_dir)
    os.makedirs(test_build_dir, exist_ok=True)

    # create dummy binaries
    dummy_artifacts = {}
    for ext in _BUILD_EXTS:
        artifact_path = os.path.join(test_build_dir, f'{testname}.{ext}')
        with open(artifact_path, 'wb') as f:
            f.write(b"-- dummy data --")
        dummy_artifacts[ext] = artifact_path

    test_spec = {
        "builds": {
            f"{target.upper()}-{toolchain.upper()}": {
                "platform": target,
                "toolchain": toolchain,
                "base_path": base_test_build_dir,
                "baud_rate": baudrate,
                "binary_type": "bootable",
                "tests": {
                    testname: {
                        "binaries": [
                            {
                                "path": dummy_artifacts["bin"]
                            }
                        ]
                    }
                },
                "test_apps": {}
            }
        }
    }
    with open(os.path.join(test_build_dir, 'test_spec.json'), 'w', encoding='utf-8') as f:
        json.dump(test_spec, f, indent=4)


def build_run_tests_dummy_mbed_cli_callback(project_dir, *, test_name, baudrate) -> Callable:
    def mbed_cli_callback(cmd_name, cmd_args, *, cwd):
        assert_that(os.path.abspath(cwd), equal_to(os.path.abspath(project_dir)))
        assert_that(cmd_name, equal_to('test'))
        assert_that(cmd_args, has_items('--greentea', '--compile', '--tests-by-name', test_name))
        _build_dummy_test(
            project_dir=project_dir,
            program_config=ProgramConfig(project_dir),
            baudrate=baudrate,
            testname=test_name
        )
        return '', 'success', 0

    return mbed_cli_callback


_SUCCESSFUL_TEST_OUTPUT = r'''
{{__version;1.3.0}}
{{__timeout;40}}
{{__host_test_name;default_auto}}
{{__testcase_count;2}}
>>> Running 2 test cases...
{{__testcase_name;test_success_1}}
{{__testcase_name;test_success_2}}

>>> Running case #1: 'test_success_1'...
{{__testcase_start;test_success_1}}
{{__testcase_finish;test_success_1;1;0}}
>>> 'test_success_1': 1 passed, 0 failed

>>> Running case #2: 'test_success_2'...
{{__testcase_start;test_success_2}}
{{__testcase_finish;test_success_2;1;0}}
>>> 'test_success_2': 1 passed, 0 failed

>>> Test cases: 2 passed, 0 failed
{{__testcase_summary;2;0}}
{{end;success}}
{{__exit;0}}
'''


@pytest.mark.base_project_dir(FIXTURE_DIR)
def test_run_successful_test(mbed_project, mbed_cli_mock):
    runner = TransparentOutputCliRunner(mix_stderr=True, env=_DEFAULT_ENV)
    mbed_cli_mock.callback = build_run_tests_dummy_mbed_cli_callback(
        project_dir=mbed_project,
        test_name=_TEST_NAME,
        baudrate=_TEST_SERIAL_SPEED
    )

    with VirtualComPortStub(
            baudrate=_TEST_SERIAL_SPEED,
            callback=build_target_test_serial_callback(_SUCCESSFUL_TEST_OUTPUT)
    ) as tty_file:
        result = runner.invoke(
            main_cli, ['run-tests', '--board-manager-script', 'target_manager.sh', '--tests-by-name', _TEST_NAME],
            env={'TEST_SERIAL_PORT': tty_file},
        )

    assert_that(result.exit_code, equal_to(0), reason=f"See: {result}")
    assert_that(result.output, string_contains_in_order(
        'test suite report',
        _TEST_TARGET_FULL_NAME, _TEST_NAME, 'OK',
        'test case report',
        _TEST_TARGET_FULL_NAME, _TEST_NAME, 'test_success_1', 'OK',
        _TEST_TARGET_FULL_NAME, _TEST_NAME, 'test_success_2', 'OK',
    ))


_FAILURE_TEST_OUTPUT = r'''
{{__version;1.3.0}}
{{__timeout;40}}
{{__host_test_name;default_auto}}
{{_
read: _testcase_count;2}}
>>> Running 2 test cases...
{{__testcase_name;test_success}}
{{__testcase_name;test_failure}}

>>> Runnin
read: g case #1: 'test_success'...
{{__testcase_start;test_success}}
{{__testcase_finish;test_success;1;0}}
>>> 'test_success': 1 passed, 0 failed

>>> Running case
read:  #2: 'test_failure'...
{{__testcase_start;test_failure}}
:47::FAIL: Expected 1 Was 0
{{__testcase_finish;test_failure;0;1}}
>>
read: > 'test_failure': 0 passed, 1 failed with reason 'Test Cases Failed'

>>> Test cases: 1 passed, 1 failed with reason 'Test Cases
read:  Failed'
>>> TESTS FAILED!
{{__testcase_summary;1;1}}
{{end;failure}}
{{__exit;0}}
'''


@pytest.mark.base_project_dir(FIXTURE_DIR)
def test_run_failure_test(mbed_project, mbed_cli_mock):
    runner = TransparentOutputCliRunner(mix_stderr=True, env=_DEFAULT_ENV)
    mbed_cli_mock.callback = build_run_tests_dummy_mbed_cli_callback(
        project_dir=mbed_project,
        test_name=_TEST_NAME,
        baudrate=_TEST_SERIAL_SPEED
    )

    with VirtualComPortStub(
            baudrate=_TEST_SERIAL_SPEED,
            callback=build_target_test_serial_callback(_FAILURE_TEST_OUTPUT)
    ) as tty_file:
        result = runner.invoke(
            main_cli, ['run-tests', '--board-manager-script', 'target_manager.sh', '--tests-by-name', _TEST_NAME],
            env={'TEST_SERIAL_PORT': tty_file},
        )

    assert_that(result.exit_code, not_(equal_to(0)), reason=f"See: {result}")
    assert_that(result.output, string_contains_in_order(
        'test suite report',
        _TEST_TARGET_FULL_NAME, _TEST_NAME, 'FAIL',
        'test case report',
        _TEST_TARGET_FULL_NAME, _TEST_NAME, 'test_failure', 'FAIL',
        _TEST_TARGET_FULL_NAME, _TEST_NAME, 'test_success', 'OK',
    ))
