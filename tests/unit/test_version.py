import subprocess
import sys

import nagbot


def test_version_string() -> None:
    assert nagbot.__version__


def test_cli_version() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "nagbot", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert nagbot.__version__ in out.stdout
