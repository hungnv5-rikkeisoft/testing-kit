from PIL import Image as PILImage
from tcformat.schema import Screen, Testcase, Result, BrowserResult, dump_screen
from tcformat.report_cli import build_report_from_yaml, main
from tcformat.resources import default_template


def _png(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    PILImage.new("RGB", (600, 400), "white").save(path)


def test_build_report_uses_bundled_template(tmp_path):
    rel = "evidence/s/chrome/UI_01/step_1.png"
    _png(tmp_path / rel)
    sc = Screen(screen="S", test_level="IT", testcases=[
        Testcase(id="UI_01", section="UI", main_item="x", type="IT",
                 priority="High",
                 result=Result(chrome=BrowserResult(status="OK", evidence=[rel]))),
    ])
    yml = tmp_path / "s.yaml"
    dump_screen(sc, yml)
    out = tmp_path / "reports" / "test_report.xlsx"
    data = build_report_from_yaml([str(yml)], default_template(), str(out),
                                  base_dir=str(tmp_path))
    assert data.executed == 1 and data.exit_ok is True
    assert out.exists()


def test_main_exits_zero_on_pass(tmp_path, monkeypatch):
    rel = "evidence/s/chrome/UI_01/step_1.png"
    _png(tmp_path / rel)
    sc = Screen(screen="S", test_level="IT", testcases=[
        Testcase(id="UI_01", section="UI", main_item="x", type="IT",
                 priority="High",
                 result=Result(chrome=BrowserResult(status="OK", evidence=[rel]))),
    ])
    yml = tmp_path / "s.yaml"
    dump_screen(sc, yml)
    out = tmp_path / "reports" / "r.xlsx"
    monkeypatch.chdir(tmp_path)
    try:
        main(["--yaml", str(yml), "--out", str(out)])
    except SystemExit as e:
        assert e.code == 0
    else:
        raise AssertionError("main did not raise SystemExit")
