import json
from tcformat.strategy import main


def test_strategy_cli_prints_json(capsys):
    main(["--sheet", "2_IntergrationTesting"])
    out = capsys.readouterr().out
    objs = json.loads(out)
    assert isinstance(objs, list) and objs
    assert any(o.get("ref") == "2.3.1#1" for o in objs)


def test_strategy_cli_handles_vietnamese(capsys):
    main(["--sheet", "2_IntergrationTesting"])
    out = capsys.readouterr().out
    objs = json.loads(out)
    # at least one object name contains a non-ASCII (Vietnamese) character
    assert any(any(ord(ch) > 127 for ch in (o.get("object") or "")) for o in objs)
