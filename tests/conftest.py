from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="regenerate golden files instead of comparing",
    )


@pytest.fixture
def golden(request: pytest.FixtureRequest) -> "GoldenComparer":
    return GoldenComparer(
        directory=Path(__file__).parent / "golden" / "files",
        update=bool(request.config.getoption("--update-golden")),
    )


class GoldenComparer:
    def __init__(self, directory: Path, update: bool) -> None:
        self.directory = directory
        self.update = update

    def check(self, name: str, content: str) -> None:
        path = self.directory / name
        normalized = content.replace("\r\n", "\n").rstrip() + "\n"
        if self.update:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(normalized)
            return
        assert path.exists(), f"golden file missing: {path} (run pytest --update-golden)"
        assert normalized == path.read_text(), (
            f"{name} differs from golden — inspect diff or run pytest --update-golden"
        )
