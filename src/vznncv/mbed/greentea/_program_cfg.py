"""
Helper module that contains helper classes to read project configuration.
"""
import functools
import os.path
import re
from typing import Optional
import vznncv.mbed.greentea._mbed_cli as mbed_cli_executor


class ProgramConfig:
    """
    Helper class to read current project from ``.mbed`` filed.
    """
    _CONFIG_FILE = '.mbed'
    _DEFAULT_BUILD_DIR = 'BUILD'
    _DEFAULT_PROFILE = 'debug'
    _PROJECT_CONF_FILE_RE = re.compile("^(?P<name>[^=]+)=(?P<value>.*)$")

    def __init__(self, project_dir):
        self._config = {}
        self._project_dir = os.path.abspath(project_dir)
        config_file = os.path.join(project_dir, '.mbed')
        if os.path.exists(config_file):
            with open(config_file, encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip()
                    if not line or line.startswith('#'):
                        continue
                    m = self._PROJECT_CONF_FILE_RE.match(line)
                    if m is None:
                        continue
                    self._config[m.group('name')] = m.group('value')

    def get_build_dir(self):
        return os.path.join(self._project_dir, self._DEFAULT_BUILD_DIR)

    def _resolve_option(self, option_name: str, cfg_name: str, explicit_value: Optional[str],
                        default_value: Optional[str] = None) -> str:
        if explicit_value:
            return explicit_value
        cfg_value = self._config.get(cfg_name)
        if cfg_value:
            return cfg_value
        if default_value:
            return default_value
        raise ValueError(f"Cannot resolve {option_name}. It isn't specified explicitly and "
                         f"isn't found in the \"{self._CONFIG_FILE}\" file ({cfg_name} record)")

    def resolve_target(self, target: Optional[str] = None) -> str:
        return self._resolve_option('target', 'TARGET', target)

    def resolve_toolchaing(self, toolchain: Optional[str] = None) -> str:
        return self._resolve_option('toolchain', 'TOOLCHAIN', toolchain)

    def resolve_profile(self, profile: Optional[str] = None) -> str:
        return self._resolve_option('profile', 'PROFILE', profile, self._DEFAULT_PROFILE)

    @property
    def program_name(self) -> str:
        return os.path.basename(self._project_dir)


class AppConfig:
    """
    Helper class to read and parse project configuration.
    """
    _CONFIG_LINE_PROBE_RE = re.compile(r'^[\w\-]+\.')
    _CONFIG_LINE_BASE_RE = re.compile(
        r'^(?P<name>[\w\-.]+)\s*(?P<value_mark>=)?\s*?(?P<value_part>.*?)(?P<macro_comment>\([^()]+\))?$'
    )

    @classmethod
    @functools.lru_cache(maxsize=8)
    def _read_config_impl(cls, project_dir: str, app_config_path: Optional[str] = None):
        mbed_args = ['compile', '--config']
        if app_config_path is not None:
            mbed_args.append(['--app-config', app_config_path])
        result = mbed_cli_executor.run_mbed_cli_command(
            mbed_args,
            project_dir=project_dir, capture_output=True, check=True, encoding='utf-8'
        )
        # extract configuration lines
        config_lines = []
        for line in result.stdout.splitlines():
            line = line.rstrip()
            m = cls._CONFIG_LINE_PROBE_RE.match(line)
            if m is not None:
                config_lines.append(line)
        # parse configuration lines
        app_config = {}
        for line in config_lines:
            m = cls._CONFIG_LINE_BASE_RE.match(line)
            if m is None:
                continue
            prop_name = m.group('name')
            value_part = m.group('value_part')
            if value_part is None:
                continue
            if m.group('value_mark') is not None:
                # property has a value
                prop_value = value_part.strip()
            elif value_part.lower().strip() == 'has no value':
                # property has not value
                prop_value = None
            else:
                # invalid line
                continue
            app_config[prop_name] = prop_value

        return app_config

    @classmethod
    def _read_config(cls, project_dir, app_config_path=None):
        project_dir = os.path.abspath(project_dir)
        if app_config_path is not None:
            app_config_path = os.path.abspath(app_config_path)
        return cls._read_config_impl(project_dir, app_config_path)

    def __init__(self, project_dir, app_config_path=None):
        self._config = self._read_config(project_dir, app_config_path)

    _NO_DEFAULT = object()

    def get_parameter(self, name, default=_NO_DEFAULT):
        value = self._config.get(name, default)
        if value is self._NO_DEFAULT:
            raise KeyError(name)
        return value
