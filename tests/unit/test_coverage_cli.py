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
    with pytest.raises(SystemExit):
        main(argv)
    assert out.exists()
    assert "technique" in out.read_text(encoding="utf-8")
