import yaml
import pytest

from tcformat.coverage_cli import main

CHECKLISTS = {
    "button": [{"technique": "single-action", "category": "Function", "title": "x"}],
    "screen": [],
}


def _setup(tmp_path, testcases, *, skip=None):
    (tmp_path / "checklists.yaml").write_text(
        yaml.safe_dump(CHECKLISTS), encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"checklists_path": str(tmp_path / "checklists.yaml")}),
        encoding="utf-8")
    el = {"id": "btn", "kind": "button"}
    if skip:
        el["skip_techniques"] = skip
    (tmp_path / "s.inventory.yaml").write_text(
        yaml.safe_dump({"screen": "S", "elements": [el]}), encoding="utf-8")
    (tmp_path / "s.yaml").write_text(
        yaml.safe_dump({"screen": "S", "testcases": testcases}), encoding="utf-8")
    return [
        "--screen", str(tmp_path / "s.yaml"),
        "--config", str(tmp_path / "config.yaml"),
    ]


def test_exit_1_on_gap(tmp_path):
    argv = _setup(tmp_path, testcases=[])   # btn/single-action uncovered
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 1


def test_exit_0_when_covered(tmp_path):
    argv = _setup(tmp_path, testcases=[
        {"id": "A", "target": "btn", "technique": "single-action"}])
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 0


def test_skip_techniques_makes_gate_pass(tmp_path):
    argv = _setup(tmp_path, testcases=[], skip=["single-action"])
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 0


def test_unknown_technique_warns_but_passes(tmp_path):
    # covered + an extra testcase with a bogus technique -> warning, still exit 0
    argv = _setup(tmp_path, testcases=[
        {"id": "A", "target": "btn", "technique": "single-action"},
        {"id": "B", "target": "btn", "technique": "bogus"}])
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 0


def test_matrix_out_written(tmp_path):
    out = tmp_path / "sub" / "matrix.md"
    argv = _setup(tmp_path, testcases=[
        {"id": "A", "target": "btn", "technique": "single-action"}])
    argv += ["--matrix-out", str(out)]
    with pytest.raises(SystemExit) as e:
        main(argv)
    assert e.value.code == 0
    assert out.exists()
    assert "technique" in out.read_text(encoding="utf-8")


def test_unicode_output_survives_non_utf8_stdout(tmp_path, monkeypatch):
    import io
    import sys
    argv = _setup(tmp_path, testcases=[])   # uncovered -> prints ✗ marker + matrix
    # Simulate a Windows cp932-style console that cannot encode ✓/✗/–
    buf = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    monkeypatch.setattr(sys, "stdout", buf)
    with pytest.raises(SystemExit) as e:
        main(argv)            # must NOT raise UnicodeEncodeError
    assert e.value.code == 1


def test_main_exits_nonzero_on_completeness_violation(tmp_path, capsys):
    import pytest
    from tcformat.coverage_cli import main
    screen = tmp_path / "s.yaml"
    screen.write_text(
        "screen: S\ntest_level: IT\ntestcases:\n"
        "  - id: T1\n    main_item: m\n    target: btn\n    technique: single-action\n"
        "    expected:\n      - {request: 'POST /'}\n",
        encoding="utf-8")
    inv = tmp_path / "s.inventory.yaml"
    inv.write_text(
        "screen: S\nelements:\n  - {id: btn, kind: button, label: B}\n",
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        main(["--screen", str(screen), "--inventory", str(inv)])
    assert e.value.code == 1
    out = capsys.readouterr().out
    assert "COMPLETENESS" in out and "R1" in out


def test_main_completeness_passes_with_declared_absent(tmp_path):
    import pytest
    import yaml
    from tcformat.coverage_cli import main
    # Use a minimal checklists (single-action only, no screen techniques) so depth
    # is clean and the test isolates completeness behavior (brief note).
    checklists = {"button": [{"technique": "single-action",
                               "category": "Function", "title": "x"}],
                  "screen": []}
    (tmp_path / "checklists.yaml").write_text(yaml.safe_dump(checklists),
                                              encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"checklists_path": str(tmp_path / "checklists.yaml")}),
        encoding="utf-8")
    screen = tmp_path / "s.yaml"
    screen.write_text(
        "screen: S\ntest_level: IT\ntestcases:\n"
        "  - id: T1\n    main_item: m\n    target: btn\n    technique: single-action\n"
        "    expected:\n      - {request: 'POST /'}\n",
        encoding="utf-8")
    inv = tmp_path / "s.inventory.yaml"
    inv.write_text(
        "screen: S\nabsent:\n  api: 'mock POST, không kiểm response'\n"
        "elements:\n  - {id: btn, kind: button, label: B}\n",
        encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        main(["--screen", str(screen), "--inventory", str(inv),
              "--config", str(tmp_path / "config.yaml")])
    # No depth gaps (single-action covered), no lint violation (api declared absent):
    assert e.value.code == 0
