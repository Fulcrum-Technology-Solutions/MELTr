"""Output Handlers module."""

from logforge.outputs.base import OutputHandler
from logforge.outputs.console import ConsoleOutputHandler
from logforge.outputs.file import FileOutputHandler
from logforge.outputs.http import HTTPOutputHandler
from logforge.outputs.syslog import SyslogOutputHandler
from logforge.outputs.tcp import TCPOutputHandler
from logforge.outputs.factory import create_output_handlers

__all__ = [
    'OutputHandler',
    'ConsoleOutputHandler',
    'FileOutputHandler',
    'HTTPOutputHandler',
    'SyslogOutputHandler',
    'TCPOutputHandler',
    'create_output_handlers',
]
