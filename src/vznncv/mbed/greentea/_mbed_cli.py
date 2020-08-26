import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


def resolve_python_cmd():
    python_cmd = sys.executable
    python_cmd_name = os.path.basename(python_cmd)
    if not python_cmd_name.startswith('python'):
        python_cmd = 'python3'
    return python_cmd


def resolve_mbed_cli_cmd():
    # if project run with "pyinstaller", always use 'mbed-cli' directly
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return ['mbed-cli']
    try:
        import mbed
    except ImportError:
        return ['mbed-cli']
    else:
        return [resolve_python_cmd(), '-u', '-m', 'mbed']


def run_mbed_cli_command(args, project_dir, *, stdout=None, stderr=None, capture_output=False,
                         check=False, encoding=None) -> subprocess.CompletedProcess:
    mbed_cli_cmd = resolve_mbed_cli_cmd()
    cli_cmd = mbed_cli_cmd + list(args)

    cli_env = os.environ.copy()
    cli_env['PWD'] = os.path.abspath(project_dir)
    kwargs = {
        'cwd': project_dir,
        'env': cli_env,
        'check': check,
        'encoding': encoding
    }
    if stdout is not None:
        kwargs['stdout'] = stdout
    if stderr is not None:
        kwargs['stderr'] = stderr
    if capture_output:
        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE

    logger.info(f"Run command: {' '.join(cli_cmd)}")
    return subprocess.run(cli_cmd, **kwargs)
