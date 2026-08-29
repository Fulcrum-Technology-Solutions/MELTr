"""Output Handlers module."""

from meltr.outputs.base import OutputHandler
from meltr.outputs.console import ConsoleOutputHandler
from meltr.outputs.factory import create_output_handlers
from meltr.outputs.file import FileOutputHandler
from meltr.outputs.http import HTTPOutputHandler
from meltr.outputs.syslog import SyslogOutputHandler
from meltr.outputs.tcp import TCPOutputHandler

__all__ = [
    "OutputHandler",
    "ConsoleOutputHandler",
    "FileOutputHandler",
    "HTTPOutputHandler",
    "SyslogOutputHandler",
    "TCPOutputHandler",
    "create_output_handlers",
]
