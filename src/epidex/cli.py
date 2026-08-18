# argument parsing, top-level orchestration (old main() from nonfondownloader.py)

# Library Dependencies Check!

import sys
import importlib.util


REQUIRED_PACKAGES = {
    "requests": "requests",
    "dotenv": "python-dotenv",
    "rich": "rich",
}
missing = [pip_name for mod, pip_name in REQUIRED_PACKAGES.items()
           if importlib.util.find_spec(mod) is None]
if missing:
    sys.exit(f"ERROR: missing required package(s): {', '.join(missing)}\n"
              f"Install with:\n    pip install {' '.join(missing)}")


# Python Module Import

import json
import math
import os
import platform
import queue
import random
import re
import requests
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from dotenv import dotenv_values
from pathlib import Path
from rich.console import Console


# Custom Modules Import

from epidex.episode import Episode
from epidex.input_panel import InputPanel
from epidex.queue_manager import QueueManager


def main():
    ...