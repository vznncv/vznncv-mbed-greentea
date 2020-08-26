import json
import logging
import os
import shutil
import subprocess
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ExternalTargetManager:
    """
    Helper wrapper around custom script that:
    - detects boards
    - flash firmware
    - reset board (optionally)
    """

    COPY_METHOD_NAME = 'external_script'
    RESET_METHOD_NAME = 'external_script'

    def __init__(self, target_manager_script):
        """

        :param target_manager_script: board manager script path or command
        """
        # 1. check if script is located in the PATH
        script_path = shutil.which(target_manager_script)
        if script_path is None:
            # 2. check if it's path to a file
            if os.path.isfile(target_manager_script):
                script_path = os.path.abspath(target_manager_script)
            else:
                raise ValueError(f"Cannot find board manager script: {target_manager_script}")

        self._target_manager_script = script_path
        self._target_to_image_format: Dict[str, str] = {}

    def _run_command(self, args: List[str], check_retcode=False):
        run_cmd = [self._target_manager_script] + args
        run_cmd_str = ' '.join(run_cmd)
        logger.info(f"Run external board manager script: {run_cmd_str}")
        result = subprocess.run(run_cmd, stdout=subprocess.PIPE, encoding='utf-8')
        if check_retcode and result.returncode:
            raise ValueError(f"Command \"{run_cmd_str}\" has failed with a code {result.returncode}")
        output = result.stdout.strip()
        if output:
            try:
                output_obj = json.loads(output)
            except Exception as e:
                raise ValueError(f"Command \"{run_cmd_str}\" has returned invalid json object:\n{output}") from e
        else:
            output_obj = None
        return output_obj, result.returncode

    _MANDATORY_VALUE = object()
    _MISSED_VALUE = object()
    _LIST_TARGETS = {
        'target_id': (str, _MANDATORY_VALUE),
        'target_name': (str, _MANDATORY_VALUE),
        'serial_port': (str, _MANDATORY_VALUE),
        'image_format': (str, _MANDATORY_VALUE),
        'reset_command': (bool, False)  # optional boolean value
    }

    def list_targets(self) -> List[Dict[str, Any]]:
        result, _ = self._run_command(['list'], check_retcode=True)
        # validate result objects
        target_list = []
        for target_info in result:
            cleared_target_info = {}
            for field_name, (value_type, default_value) in self._LIST_TARGETS.items():
                field_value = target_info.get(field_name, self._MISSED_VALUE)
                if field_value is self._MISSED_VALUE:
                    if default_value is self._MANDATORY_VALUE:
                        raise ValueError(f"Record:\n"
                                         f"{json.dumps(target_info, indent=4)}\n"
                                         f"doesn't have mandatory field \"{field_name}\"")
                    else:
                        field_value = default_value
                if not isinstance(field_value, value_type):
                    raise ValueError(f"Expect that field \"{field_name}\" in the record:\n"
                                     f"{json.dumps(target_info, indent=4)}\n"
                                     f"has \"{value_type.__name__}\" type, "
                                     f"but it was \"{type(field_value)}\" (\"{field_value}\")")
                cleared_target_info[field_name] = field_value
            # save expected image format
            target_id = cleared_target_info['target_id']
            self._target_to_image_format[target_id] = cleared_target_info['image_format']
            target_list.append(cleared_target_info)
        return target_list

    def flash_target(self, target_id: str, image_path: str):
        image_format = self._target_to_image_format.get(target_id)
        if image_format is None:
            raise ValueError(f"Cannot resolve expected image format for target \"{image_format}\"")
        image_path = os.path.abspath(image_path)
        image_base_path, image_ext = os.path.splitext(image_path)
        image_ext = image_ext.lstrip('.')
        if image_ext != image_format:
            # try to find expected image format
            image_updated_path = f'{image_base_path}.{image_format}'
            if not os.path.isfile(image_updated_path):
                raise ValueError(f"Cannot find a firmware image \"{image_updated_path}\"")
            image_path = image_updated_path
        self._run_command(['flash', '--target-id', target_id, '--image-path', image_path], check_retcode=True)

    def reset_target(self, target_id: str):
        self._run_command(['reset', '--target-id', target_id], check_retcode=True)
