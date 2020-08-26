import os.path
import os.path
from typing import Callable

import pytest
from hamcrest import assert_that, equal_to, not_, string_contains_in_order, has_item

from testing_utils import VirtualComPortStub, TransparentOutputCliRunner, build_target_test_serial_callback
from vznncv.mbed.greentea._cli import main as main_cli

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'simple_project')

_TEST_TARGET_NAME = 'BLACKPILL_F401CC'
_TEST_TARGET_ID = 'FFFF00000000000000000000'
_TEST_SERIAL_PORT = '/dev/ttyUSB0'
_TEST_IMAGE_FORAT = 'elf'
_TEST_RESET_METHOD = 'true'
_TEST_TARGET_IS_CONNECTED = '1'
_TEST_SERIAL_SPEED = 9600

_DEFAULT_ENV = {
    'TEST_TARGET_NAME': _TEST_TARGET_NAME,
    'TEST_TARGET_ID': _TEST_TARGET_ID,
    'TEST_SERIAL_PORT': _TEST_SERIAL_PORT,
    'TEST_IMAGE_FORMAT': _TEST_IMAGE_FORAT,
    'TEST_RESET_METHOD': _TEST_RESET_METHOD,
    'TEST_TARGET_IS_CONNECTED': _TEST_TARGET_IS_CONNECTED
}


def build_debug_test_dummy_mbed_cli_callback(project_dir, *, baudrate) -> Callable:
    def mbed_cli_callback(cmd_name, cmd_args, *, cwd):
        assert_that(os.path.abspath(cwd), equal_to(os.path.abspath(project_dir)))
        assert_that(cmd_name, equal_to('compile'))
        assert_that(cmd_args, has_item('--config'))

        return '', \
               f'Configuration parameters\n' \
               f'------------------------\n' \
               f'platform.stdio-baud-rate = {baudrate} (macro name: macro name: "MBED_CONF_PLATFORM_STDIO_BAUD_RATE")\n' \
               f'\n' \
               f'Macros\n' \
               f'------\n' \
               f'\n', 0

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
    mbed_cli_mock.callback = build_debug_test_dummy_mbed_cli_callback(
        project_dir=mbed_project,
        baudrate=_TEST_SERIAL_SPEED
    )

    with VirtualComPortStub(
            baudrate=_TEST_SERIAL_SPEED,
            callback=build_target_test_serial_callback(_SUCCESSFUL_TEST_OUTPUT)
    ) as tty_file:
        result = runner.invoke(
            main_cli, ['debug-test', '--board-manager-script', 'target_manager.sh'],
            env={'TEST_SERIAL_PORT': tty_file},
        )

    assert_that(result.exit_code, equal_to(0), reason=f"See: {result}")
    assert_that(result.output, string_contains_in_order(
        '{{__testcase_start;test_success_1}}',
        '{{__testcase_finish;test_success_1;1;0}}',
        '{{__testcase_start;test_success_2}}',
        '{{__testcase_finish;test_success_2;1;0}}',
        '{{result;success}}',
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
    mbed_cli_mock.callback = build_debug_test_dummy_mbed_cli_callback(
        project_dir=mbed_project,
        baudrate=_TEST_SERIAL_SPEED
    )

    with VirtualComPortStub(
            baudrate=_TEST_SERIAL_SPEED,
            callback=build_target_test_serial_callback(_FAILURE_TEST_OUTPUT)
    ) as tty_file:
        result = runner.invoke(
            main_cli, ['debug-test', '--board-manager-script', 'target_manager.sh'],
            env={'TEST_SERIAL_PORT': tty_file},
        )

    assert_that(result.exit_code, not_(equal_to(0)), reason=f"See: {result}")
    assert_that(result.output, string_contains_in_order(
        '{{__testcase_start;test_success}}',
        '{{__testcase_finish;test_success;1;0}}',
        '{{__testcase_start;test_failure}}',
        '{{__testcase_finish;test_failure;0;1}}',
        '{{result;failure}}',
    ))
