import io
import logging
import os
import re
import sys
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import TextIO, List, Dict, Generator, Optional

logger = logging.getLogger(__name__)


@contextmanager
def patch_cwd(new_cwd):
    prev_dir = os.getcwd()
    try:
        os.chdir(new_cwd)
        yield
    finally:
        os.chdir(prev_dir)


@contextmanager
def patch_argv(new_argv):
    prev_argv = sys.argv.copy()
    try:
        sys.argv[:] = new_argv
        yield
    finally:
        sys.argv[:] = prev_argv


@contextmanager
def chain_patches(patches):
    applied_patches = []
    try:
        for patch in patches:
            patch.start()
            applied_patches.append(patch)
        yield
    finally:
        first_exception = None
        for patch in reversed(applied_patches):
            try:
                patch.stop()
            except Exception as e:
                if first_exception is None:
                    first_exception = e
                logger.exception(f"Fail to stop patch: {patch}")
        # re-raise first exception
        if first_exception is not None:
            raise first_exception


class FDRedirectionCallback(ABC):
    """
    Callback interface for :fun:`inject_callback_into_output_file_descriptors` function
    """

    @abstractmethod
    def start(self, original_fds: Dict[int, int]) -> None:
        """
        Redirection startup signals.

        It accepts dictionary that contains original filed descriptors as keys and cloned filed descriptors as values.
        Cloned file descriptors are connected to sink that was used by original ones.

        :param original_fds:
        """
        pass

    @abstractmethod
    def consume(self, original_fd: int, data: bytes) -> None:
        """
        Consume redirected data.

        This method can be invoked from multiple threads, so implementation should care about thread safety.

        :param fd: original filed descriptor. It cannot be used to write data, but can be used to identify data source.
        :param data: data block
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        Redirection stop signal.

        It can be used to flush internal buffers.
        """
        pass


_MAX_PIPE_READ = 16 * 1024


def _pipe_callback_thread(pipe_fd_r: int, output_fd: int, callback: FDRedirectionCallback):
    while True:
        # read data
        try:
            data = os.read(pipe_fd_r, _MAX_PIPE_READ)
        except:
            data = b''
        # stop thread if there is no more data
        if not data:
            break
        # pass data to callback
        try:
            callback.consume(output_fd, data)
        except Exception:
            break

    # continue data reading in case of callback error
    while data:
        try:
            data = os.read(pipe_fd_r, _MAX_PIPE_READ)
        except Exception:
            break


@contextmanager
def inject_callback_into_output_file_descriptors(output_fds: List[int], callback: FDRedirectionCallback):
    """

    :param output_fds:
    :param callback:
    :return:
    """
    # clone original file descriptors to save them
    cloned_fds = {output_fd: os.dup(output_fd) for output_fd in output_fds}
    # create pipes to replace output_fds
    redirection_pipes = {output_fd: os.pipe() for output_fd in output_fds}
    # pipe threads
    pipe_threads = {}
    try:
        # prepare user callback
        callback.start(cloned_fds.copy())
        # prepare threads and reconnect file descriptors
        for output_fd in output_fds:
            cloned_fd = cloned_fds[output_fd]
            pipe_fd_r, pipe_fd_w = redirection_pipes[output_fd]

            # prepare thread
            pipe_thread = threading.Thread(
                name=f'redirect_fd_thread_fd{output_fd}_pw{pipe_fd_w}_pr{pipe_fd_r}_cfd{cloned_fd}',
                target=_pipe_callback_thread,
                args=(pipe_fd_r, output_fd, callback),
                daemon=True
            )
            pipe_thread.start()
            pipe_threads[output_fd] = pipe_thread
            # reconnect file descriptors
            os.dup2(pipe_fd_w, output_fd)

        # pass control to external code
        yield
    finally:
        # restore original file descriptors and close pip inputs
        for output_fd in reversed(output_fds):
            # restore descriptors
            os.dup2(cloned_fds[output_fd], output_fd)
            # close pipe inputs
            os.close(redirection_pipes[output_fd][1])
        # wait "pipe" threads shutdown
        for output_fd in reversed(output_fds):
            pipe_thread = pipe_threads.get(output_fd)
            if pipe_thread is None:
                continue
            pipe_thread.join()
        # close pipe outputs
        for output_fd in reversed(output_fds):
            os.close(redirection_pipes[output_fd][0])
        # close callback
        try:
            callback.stop()
        finally:
            # close cloned file descriptors
            for output_fd in reversed(output_fds):
                os.close(cloned_fds[output_fd])


class FDRedirectionTextLineCallback(FDRedirectionCallback):
    """
    Helper subclass of :class:`FDRedirectionCallback` to process text streams by lines.
    """
    _NEWLINE_RE = re.compile(b'\r\n|\r|\n')

    def __init__(self, *, encoding='utf-8', errors='replace'):
        self._sinks: Optional[Dict[int, TextIO]] = None
        self._line_bufs: Optional[Dict[int, List[bytes]]] = None
        self._original_fds: Optional[Dict[int, int]] = None
        self._encoding = encoding
        self._errors = errors

    def start(self, original_fds: Dict[int, int]) -> None:
        if self._sinks is not None:
            raise ValueError("start method was called before")
        self._original_fds = original_fds
        self._sinks = {
            original_fd: open(cloned_fd, 'w', encoding=self._encoding, closefd=False)
            for original_fd, cloned_fd in self._original_fds.items()
        }
        self._line_bufs = {original_fd: [] for original_fd in self._original_fds}

    def consume(self, original_fd: int, data: bytes) -> None:
        line_buf = self._line_bufs[original_fd]
        prev_part, *line_parts = self._NEWLINE_RE.split(data)

        line_buf.append(prev_part)
        for next_line_part in line_parts:
            text_line = b''.join(line_buf).decode(self._encoding, errors=self._errors)
            line_buf.clear()
            self.consume_line(original_fd, text_line)
            line_buf.append(next_line_part)

    def get_sink(self, original_fd) -> TextIO:
        """
        Get text IO wrapper around sink of ``original_fd``.

        This wrapper may buffer data, so if it's needed, you should call ``flush`` method explicitly.

        :param original_fd:
        :return:
        """
        return self._sinks[original_fd]

    @abstractmethod
    def consume_line(self, original_fd, line: str) -> None:
        """
        Consume text line from ``original_fd``.

        :meth:`get_sink` can be used to get stream to write data.

        :param original_fd:
        :param line:
        :return:
        """
        pass

    def stop(self) -> None:
        if self._sinks is None:
            raise ValueError("start method wasn't called before")
        # flush buffers
        for original_fd, line_buf in self._line_bufs.items():
            text_line = b''.join(line_buf).decode(self._encoding, errors='replace')
            line_buf.clear()
            self.consume_line(original_fd, text_line)
        self._line_bufs = None
        # flush and close streams
        for original_fd, sink in self._sinks.items():
            sink.close()
        # cleanup fields
        self._sinks = None
        self._original_fds = None
