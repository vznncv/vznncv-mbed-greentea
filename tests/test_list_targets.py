import json
import os.path

import pytest
from click.testing import CliRunner
from hamcrest import assert_that, empty, equal_to, contains_inanyorder, has_entries

from vznncv.mbed.greentea._cli import main as main_cli

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'simple_project')

_TEST_TARGET_NAME = 'BLACKPILL_F401CC'
_TEST_TARGET_ID = 'FFFF00000000000000000000'
_TEST_SERIAL_PORT = '/dev/ttyUSB0'
_TEST_IMAGE_FORMAT = 'elf'
_TEST_RESET_METHOD = 'true'
_TEST_TARGET_IS_CONNECTED = '0'

_DEFAULT_ENV = {
    'TEST_TARGET_NAME': _TEST_TARGET_NAME,
    'TEST_TARGET_ID': _TEST_TARGET_ID,
    'TEST_SERIAL_PORT': _TEST_SERIAL_PORT,
    'TEST_IMAGE_FORMAT': _TEST_IMAGE_FORMAT,
    'TEST_RESET_METHOD': _TEST_RESET_METHOD,
    'TEST_TARGET_IS_CONNECTED': _TEST_TARGET_IS_CONNECTED
}


@pytest.mark.base_project_dir(FIXTURE_DIR)
def test_list_no_custom_targets(mbed_project):
    runner = CliRunner(mix_stderr=False, env=_DEFAULT_ENV)
    result = runner.invoke(
        main_cli, ['list-targets', '--json', '--board-manager-script', 'target_manager.sh'],
        env={'TEST_TARGET_IS_CONNECTED': '0'}
    )
    assert_that(result.exit_code, equal_to(0), reason=f"See: {result.stderr}")
    target_infos = json.loads(result.stdout)
    target_infos = [target_info for target_info in target_infos if target_info['platform_name'] == _TEST_TARGET_NAME]
    assert_that(target_infos, empty())


@pytest.mark.base_project_dir(FIXTURE_DIR)
def test_list_with_custom_targets(mbed_project):
    runner = CliRunner(mix_stderr=False, env=_DEFAULT_ENV)

    result = runner.invoke(
        main_cli, ['list-targets', '--json', '--board-manager-script', 'target_manager.sh'],
        env={'TEST_TARGET_IS_CONNECTED': '1'}
    )
    assert_that(result.exit_code, equal_to(0), reason=f"See: {result.stderr}")
    target_infos = json.loads(result.stdout)
    target_infos = [target_info for target_info in target_infos if target_info['platform_name'] == _TEST_TARGET_NAME]
    assert_that(target_infos, contains_inanyorder(has_entries(
        target_id=_TEST_TARGET_ID,
        platform_name=_TEST_TARGET_NAME,
        serial_port=_TEST_SERIAL_PORT,
    )))


@pytest.mark.base_project_dir(FIXTURE_DIR)
def test_list_without_custom_target_script(mbed_project):
    runner = CliRunner(mix_stderr=False, env=_DEFAULT_ENV)
    result = runner.invoke(
        main_cli, ['list-targets', '--json'],
        env={'TEST_TARGET_IS_CONNECTED': '1'}
    )
    assert_that(result.exit_code, equal_to(0), reason=f"See: {result.stderr}")
    target_infos = json.loads(result.stdout)
    target_infos = [target_info for target_info in target_infos if target_info['platform_name'] == _TEST_TARGET_NAME]
    assert_that(target_infos, empty())
