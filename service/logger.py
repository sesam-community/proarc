"""
Logging set up
"""
import logging
import sys
import os


def logger():
    """
    Setting upp root and zeep logger
    :return: root logger object
    """
    root_logger = logging.getLogger()
    level = logging.getLevelName(os.environ.get('logLevelDefault', 'INFO'))
    root_logger.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    zeep_logger = logging.getLogger('proarc')
    zeep = logging.getLevelName(os.environ.get('logLevelZeep', 'CRITICAL'))
    zeep_logger.setLevel(zeep)

    return root_logger
