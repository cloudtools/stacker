from logging import Formatter
from colorama.ansi import Fore


class ColorFormatter(Formatter):

    def format(self, record):
        if 'color' not in record.__dict__:
            record.__dict__['color'] = Fore.WHITE
        msg = super(ColorFormatter, self).format(record)
        return msg + Fore.RESET
