r"""PyUSB - Easy USB access in Python

This package exports the following modules and subpackages:

    core - the main USB implementation
    legacy - the compatibility layer with 0.x version
    backend - the support for backend implementations.
    control - USB standard control requests.
    libloader - helper module for backend library loading.

Since version 1.0, main PyUSB implementation lives in the 'usb.core'
module. New applications are encouraged to use it.
"""

import logging
import os

__author__ = 'Wander Lairson Costa'

# Use Semantic Versioning, http://semver.org/
version_info = (1, 0, 2)
__version__ = '%d.%d.%d' % version_info

__all__ = ['legacy', 'control', 'core', 'backend', 'util', 'libloader']

def _setup_log():
    from usb import _debug
    logger = logging.getLogger('usb')
    debug_level = os.getenv('PYUSB_DEBUG')

    if debug_level is not None:
        _debug.enable_tracing(True)
        filename = os.getenv('PYUSB_LOG_FILENAME')

        LEVELS = {'debug': logging.DEBUG,
                  'info': logging.INFO,
                  'warning': logging.WARNING,
                  'error': logging.ERROR,
                  'critical': logging.CRITICAL}

        level = LEVELS.get(debug_level, logging.CRITICAL + 10)
        logger.setLevel(level = level)

        try:
            handler = logging.FileHandler(filename)
        except:
            handler = logging.StreamHandler()

        fmt = logging.Formatter('%(asctime)s %(levelname)s:%(name)s:%(message)s')
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    else:
        class NullHandler(logging.Handler):
            def emit(self, record):
                pass

        # We set the log level to avoid delegation to the
        # parent log handler (if there is one).
        # Thanks to Chris Clark to pointing this out.
        logger.setLevel(logging.CRITICAL + 10)

        logger.addHandler(NullHandler())


_setup_log()

# We import all 'legacy' module symbols to provide compatibility
# with applications that use 0.x versions.
from usb.legacy import *
