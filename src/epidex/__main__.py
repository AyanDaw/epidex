# enables `python -m epidex` as a fallback entry point

# Library Dependencies Check!

import importlib.util
import sys

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


from epidex import cli

if __name__ == "__main__":
    cli.main()