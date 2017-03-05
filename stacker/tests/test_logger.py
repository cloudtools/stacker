from logging import makeLogRecord
import unittest
import uuid

from colorama.ansi import (
    Cursor,
    Fore,
    clear_line,
)
from mock import (
    MagicMock,
    patch,
)

from stacker.logger import (
    setup_logging,
    BASIC_LOGGER_TYPE,
    LOOP_LOGGER_TYPE,
)

from stacker.logger.handler import LogLoopStreamHandler
from stacker.logger.formatter import ColorFormatter


class TestLogStreamLoopHandler(unittest.TestCase):

    def setUp(self):
        self.stream = MagicMock()
        self.handler = LogLoopStreamHandler(self.stream)

    @patch('stacker.logger.sys')
    @patch('stacker.logger.logging')
    def test_setup_logging(self, patched_logging, patched_sys):
        patched_sys.stdout.isatty.return_value = True
        logger = setup_logging(verbosity=0, interactive=False)
        self.assertEqual(logger, LOOP_LOGGER_TYPE)
        logger = setup_logging(verbosity=1, interactive=False)
        self.assertEqual(logger, BASIC_LOGGER_TYPE)
        logger = setup_logging(verbosity=0, interactive=True)
        self.assertEqual(logger, BASIC_LOGGER_TYPE)
        patched_sys.stdout.isatty.return_value = False
        logger = setup_logging(verbosity=0, interactive=False)
        self.assertEqual(logger, BASIC_LOGGER_TYPE)

    def test_emit_normal_record(self):
        record = makeLogRecord({'msg': 'test'})
        self.handler.emit(record)
        self.assertEqual(self.stream.write.call_count, 1)
        self.assertEqual(self.stream.write.call_args[0][0], 'test\n')

    def test_emit_loop_record(self):
        loop = 0
        loop_id = uuid.uuid4()
        while loop < 2:
            for i in range(3):
                record = makeLogRecord({
                    'msg': 'test {}'.format(i),
                    'loop': loop_id,
                    'reset': i == 0,
                })
                self.handler.emit(record)
            loop += 1

        self.assertEqual(len(self.stream.write.call_args_list), 7,
                         'Should have accounted for moving cursor up')

        for index, arg in enumerate(self.stream.write.call_args_list):
            line = arg[0][0]
            if index == 3:
                self.assertTrue(line.startswith(Cursor.UP(4)))
            else:
                self.assertTrue(line.startswith(clear_line()))


class TestColorFormatter(unittest.TestCase):

    def setUp(self):
        self.formatter = ColorFormatter()

    def test_always_end_in_reset(self):
        record = makeLogRecord({'msg': 'test'})
        fmt = self.formatter.format(record)
        self.assertTrue(fmt.endswith(Fore.RESET))
