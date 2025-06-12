import sys
import logging

from libs.ui.initialize import prepare_ui
from libs.rpath import resource_path

__appname__ = 'ADPKD Support Tool'


def main():
    app, _win = prepare_ui(
        appname=__appname__,
        icon=resource_path('icon.png'),
        scriptPath=__file__,
    )
    ret = app.exec()
    _win.segmenter_thread.terminate()
    _win.detector_thread.terminate()
    return ret


if __name__ == '__main__':
    logging.basicConfig(
        filename='applog.txt',
        filemode='w',
        format='%(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    sys.exit(main())
