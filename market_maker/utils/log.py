import logging
import os
from logging.handlers import TimedRotatingFileHandler
from market_maker.settings import settings

loggers = {}


def setup_custom_logger(name, log_level=settings.LOG_LEVEL):
    if loggers.get(name):
        return loggers[name]

    if not os.path.exists('./logs'):
        os.mkdir('logs')

    logger = logging.getLogger(name)
    loggers[name] = logger

    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.setLevel(log_level)

    fh = TimedRotatingFileHandler(f'./logs/{name}.log', when='midnight', backupCount=100)
    fh.setLevel(logging.DEBUG)

    logger.addHandler(handler)
    return logger
