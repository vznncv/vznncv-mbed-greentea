import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from io import StringIO
from typing import Optional, Callable, List, Iterator, TextIO, Dict

from click.testing import CliRunner

from vznncv.mbed.greentea._utils import FDRedirectionTextLineCallback, \
    inject_callback_into_output_file_descriptors


class VirtualComPortStub:
    @staticmethod
    def _echo_callback(line):
        yield line

    def __init__(self, baudrate: int, callback: Optional[Callable[[str], Iterator[str]]] = None):
        self._baudrate = baudrate
        self._callback = callback
        if self._callback is None:
            self._callback = self._echo_callback

        self._stop_flag = False
        self._socat_communication_thread = None
        self._socat_proc = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        self._check_socat()
        if self._socat_proc is not None:
            raise ValueError("VCOM is running")
        self._stop_flag = False
        # prepare "dummy" serial port
        fd, tty_file = tempfile.mkstemp(prefix='ttyV')
        os.close(fd)
        # run socat
        self._socat_proc = subprocess.Popen(
            ['socat', '-d', '-d', f'PTY,link={tty_file},rawer,b{self._baudrate}', 'STDIO'],
            encoding='utf-8',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE
        )
        # check if socat is started without errors
        time.sleep(0.5)
        if self._socat_proc.poll() is not None:
            socat_stdout = self._socat_proc.stdout.read()
            socat_stderr = self._socat_proc.stderr.read()
            raise ValueError(f"Fail to create virtual serial port with socat:\n"
                             f"returncode: {self._socat_proc.returncode}\n"
                             f"stdout:\n{socat_stdout}\n"
                             f"stderr:\n{socat_stderr}")

        self._socat_communication_thread = threading.Thread(
            target=self._communication_thread,
            kwargs=dict(
                socat_proc=self._socat_proc,
                callback=self._callback
            ),
            daemon=True
        )
        self._socat_communication_thread.start()

        return tty_file

    def stop(self):
        if self._socat_proc is None:
            raise ValueError("VCOM isn't running")
        self._stop_flag = True

        self._socat_proc.terminate()
        self._socat_communication_thread.join()

        self._socat_proc = None
        self._socat_communication_thread = None

    def _check_socat(self):
        result = subprocess.run(['socat', '-V'], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        if result.returncode:
            raise ValueError("Please install socat to run a test")

    def _communication_thread(self, socat_proc: subprocess.Popen, callback: Callable[[str], List[str]]):
        while not self._stop_flag and socat_proc.poll() is None:
            try:
                input_line = socat_proc.stdout.readline().rstrip('\n')
            except Exception:
                break
            output_lines = callback(input_line)
            try:
                for line in output_lines:
                    socat_proc.stdin.write(line + '\n')
                    socat_proc.stdin.flush()
            except Exception:
                break


class _OutputRedirectionCallback(FDRedirectionTextLineCallback):
    def __init__(self, output_streams: Dict[int, TextIO], **kwargs):
        super().__init__(**kwargs)
        self.output_streams = output_streams
        self._consume_lock = threading.Lock()

    def consume_line(self, original_fd, line: str) -> None:
        output_stream = self.output_streams[original_fd]
        with self._consume_lock:
            output_stream.write(line + '\n')
            output_stream.flush()


class TransparentOutputCliRunner(CliRunner):
    @contextmanager
    def isolation(self, *args, **kwargs):
        prev_stdout = sys.stdout
        prev_stderr = sys.stderr
        prev_stdout_fileno = prev_stdout.fileno()
        prev_stderr_fileno = prev_stderr.fileno()
        prev_stdout.flush()
        prev_stderr.flush()

        stdout_buf = StringIO()
        if self.mix_stderr:
            stderr_buf = stdout_buf
        else:
            stderr_buf = StringIO()

        with super().isolation(*args, **kwargs) as result:
            new_stdout = sys.stdout
            new_stderr = sys.stderr
            sys.stdout = prev_stdout
            sys.stderr = prev_stderr
            output_fds = [prev_stdout_fileno, prev_stderr_fileno]
            callback = _OutputRedirectionCallback(
                output_streams={
                    prev_stdout_fileno: stdout_buf,
                    prev_stderr_fileno: stderr_buf
                },
                encoding=self.charset
            )

            try:
                with inject_callback_into_output_file_descriptors(output_fds, callback=callback):
                    yield result
            finally:
                sys.stdout = new_stdout
                sys.stderr = new_stderr

                self._stdout_invokation_result = stdout_buf.getvalue()
                self._stderr_invokation_result = stderr_buf.getvalue()

    def invoke(self, *args, **kwargs):
        result = super().invoke(*args, **kwargs)

        # note: _stdout_invokation_result and _stderr_invokation_result attributes must be set by isolation method
        stdout_text = self._stdout_invokation_result
        del self._stdout_invokation_result
        stderr_text = self._stderr_invokation_result
        del self._stderr_invokation_result

        # update result
        result.stdout_bytes = stdout_text.encode(self.charset)
        if not self.mix_stderr:
            result.stderr_bytes = stderr_text.encode(self.charset)

        return result


_SYNC_RE = re.compile(r'{{__sync;[\w-]+}}')


def build_target_test_serial_callback(test_response: str) -> Callable[[str], Iterator[str]]:
    test_finish_flag = False
    response_lines = test_response.strip().splitlines()

    def target_serial_callback(line: str) -> Iterator[str]:
        nonlocal test_finish_flag
        if test_finish_flag:
            return []
        m = _SYNC_RE.search(line)
        if m is None:
            yield "mbedmbedmbedmbedmbedmbedmbedmbed"
        else:
            test_finish_flag = True
            # sync echo
            yield m.group()
            # response  lines
            for test_line in response_lines:
                yield test_line

    return target_serial_callback
