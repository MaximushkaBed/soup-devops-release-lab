import json
import sys
from datetime import datetime

import pytest

from soup_release_lab.cli import main, report


def test_report_uses_resource_and_utc():
    result = report("Soup")
    assert result["greeting"] == "Hello, Soup!"
    assert result["version"] == "0.9.4"
    assert result["user"]
    assert datetime.fromisoformat(result["timestamp"]).utcoffset().total_seconds() == 0


def test_cli_json(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["soup-release", "--name", "Soup", "--json"])
    main()
    assert json.loads(capsys.readouterr().out)["greeting"] == "Hello, Soup!"


def test_invalid_option(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["soup-release", "--unknown"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
