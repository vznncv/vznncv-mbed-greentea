import os
import os.path
import shutil
import subprocess
import sys
import tempfile
from typing import Optional, Callable, Tuple
from unittest.mock import patch

import pytest


def pytest_configure(config):
    import logging
    logging.basicConfig(level=logging.INFO)

    config.addinivalue_line(
        "markers", "base_project_dir(path): mark directory with test data"
    )


@pytest.fixture(scope="function")
def mbed_project(request):
    marker = request.node.get_closest_marker("base_project_dir")
    if marker is None:
        raise ValueError("pytest.mark.base_project_dir(\"<project_dir>\") isn't specified")
    base_project_dir = marker.args[0]
    temp_dir = tempfile.mkdtemp(prefix='test_')
    try:
        dst_dir = os.path.join(temp_dir, os.path.basename(base_project_dir))
        shutil.copytree(base_project_dir, dst_dir)
        prev_workdir = os.getcwd()
        os.chdir(dst_dir)
        yield dst_dir
    finally:
        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)
        os.chdir(prev_workdir)


class _MbedCliMock:
    def __init__(self):
        # callback(command_name, command_args, *, cwd)
        self.callback: Optional[Callable[..., Tuple[str, str, int]]] = None

    def run_mbed_cli_command(self, args, project_dir, *, stdout=None, stderr=None, capture_output=False,
                             check=False, encoding=None) -> subprocess.CompletedProcess:
        if capture_output:
            stdout = subprocess.PIPE
            stderr = subprocess.PIPE

        cmd = args[0]
        cmd_args = args[1:]
        cmd_stderr, cmd_stdout, exit_code = self.callback(cmd, cmd_args, cwd=project_dir)

        if stderr == subprocess.PIPE:
            stderr = cmd_stderr
        elif stderr is None:
            print(stderr, file=sys.stderr)
        else:
            stderr = None
        if stdout == subprocess.PIPE:
            stdout = cmd_stdout
        elif stdout is None:
            print(stdout, file=sys.stdout)
        else:
            stdout = None

        result = subprocess.CompletedProcess(['mbed-cli'] + args, returncode=exit_code, stdout=stdout, stderr=stderr)
        if check:
            result.check_returncode()
        return result


@pytest.fixture(scope='function')
def mbed_cli_mock():
    mock = _MbedCliMock()
    import vznncv.mbed.greentea._mbed_cli as mbed_cli_executor
    with patch.object(mbed_cli_executor, 'run_mbed_cli_command', mock.run_mbed_cli_command):
        yield mock
