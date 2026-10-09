"""WSGI entrypoint for Namecheap cPanel "Setup Python App" (Phusion Passenger).

cPanel points Passenger at this file; it must expose a module-level callable
named ``application``.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from threatintel.web.app import create_app  # noqa: E402

application = create_app()
