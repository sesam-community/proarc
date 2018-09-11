import logging
import sys
import os

def Logger():
    #setting loglevel for root
    rootLogger = logging.getLogger()
    level = logging.getLevelName(os.environ.get('logLevelDefault', 'INFO'))
    rootLogger.setLevel(level)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    rootLogger.addHandler(ch)

    #setting loglevel for zeep package
    zeepLogger = logging.getLogger('proarc')
    zeep = logging.getLevelName(os.environ.get('logLevelZeep', 'CRITICAL'))
    zeepLogger.setLevel(zeep)

    return rootLogger