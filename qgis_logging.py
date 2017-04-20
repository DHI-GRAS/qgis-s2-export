import logging

class ProgressHandler(logging.StreamHandler):

    def __init__(self, progress):
        super(self.__class__, self).__init__()
        self.progress = progress

    def emit(self, record):
        msg = self.format(record)
        self.progress.setConsoleInfo(msg)


def set_progress_logger(name, progress, level='INFO'):
    logger = logging.getLogger(name)
    progress_handler = ProgressHandler(progress)
    logger.setHandler(progress_handler)
    logger.setLevel(level)
    return logger
