import pytest
from pathlib import Path
from tcformat.schema import load_screen
from tcformat import runlog

YAML = (
    "screen: Basic Info\n"
    "testcases:\n"
    "  - id: UI_01\n    type: IT\n    priority: High\n"
    "  - id: FN_01\n    type: IT\n    priority: High\n"
)


def _write(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text(YAML, encoding="utf-8")
    return p


def test_evidence_dir_created(tmp_path):
    d = runlog.evidence_dir("basic-info", "chrome", "UI_01", root=str(tmp_path / "ev"))
    assert d.exists() and d.is_dir()
    assert d.parts[-3:] == ("basic-info", "chrome", "UI_01")


def test_evidence_dir_bad_browser(tmp_path):
    with pytest.raises(ValueError):
        runlog.evidence_dir("s", "edge", "UI_01", root=str(tmp_path))


def test_record_result_roundtrip(tmp_path):
    p = _write(tmp_path)
    runlog.record_result(p, "UI_01", "chrome", "OK",
                         evidence=["a.png", "b.png"], tester="bot", date="2026-06-15")
    sc = load_screen(p)
    tc = next(t for t in sc.testcases if t.id == "UI_01")
    assert tc.result.chrome.status == "OK"
    assert tc.result.chrome.evidence == ["a.png", "b.png"]
    assert tc.result.chrome.tester == "bot"
    fn = next(t for t in sc.testcases if t.id == "FN_01")
    assert fn.result.chrome.status is None


def test_record_result_ng_with_note(tmp_path):
    p = _write(tmp_path)
    runlog.record_result(p, "FN_01", "chrome", "NG", note="validate không hiện")
    sc = load_screen(p)
    fn = next(t for t in sc.testcases if t.id == "FN_01")
    assert fn.result.chrome.status == "NG"
    assert fn.result.chrome.note == "validate không hiện"


def test_record_result_bad_status(tmp_path):
    p = _write(tmp_path)
    with pytest.raises(ValueError):
        runlog.record_result(p, "UI_01", "chrome", "PASS")


def test_record_result_bad_browser(tmp_path):
    p = _write(tmp_path)
    with pytest.raises(ValueError):
        runlog.record_result(p, "UI_01", "edge", "OK")


def test_record_result_unknown_id(tmp_path):
    p = _write(tmp_path)
    with pytest.raises(ValueError):
        runlog.record_result(p, "ZZ_99", "chrome", "OK")


def test_cli_evidence_dir(tmp_path, capsys):
    runlog.main(["evidence-dir", "--screen", "s", "--browser", "chrome",
                 "--id", "T1", "--root", str(tmp_path / "ev")])
    out = capsys.readouterr().out.strip()
    assert out.endswith(str(Path("s") / "chrome" / "T1"))
    assert (tmp_path / "ev" / "s" / "chrome" / "T1").is_dir()


def test_cli_record(tmp_path):
    p = _write(tmp_path)
    runlog.main(["record", "--yaml", str(p), "--id", "UI_01",
                 "--browser", "chrome", "--status", "OK",
                 "--evidence", "x.png"])
    sc = load_screen(p)
    tc = next(t for t in sc.testcases if t.id == "UI_01")
    assert tc.result.chrome.status == "OK"
    assert tc.result.chrome.evidence == ["x.png"]
