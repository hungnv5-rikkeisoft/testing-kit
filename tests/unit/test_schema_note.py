from tcformat.schema import load_screen, dump_screen, VALID_STATUSES, BrowserResult


def test_browser_result_has_note_default():
    assert BrowserResult().note is None


def test_valid_statuses_set():
    assert VALID_STATUSES == {"OK", "NG", "N/A"}


def test_note_roundtrip(tmp_path):
    y = (
        "screen: S\n"
        "testcases:\n"
        "  - id: UI_01\n"
        "    type: IT\n"
        "    priority: Low\n"
        "    result:\n"
        "      chrome:\n"
        "        status: NG\n"
        "        note: 'validate sai'\n"
    )
    p = tmp_path / "s.yaml"
    p.write_text(y, encoding="utf-8")
    sc = load_screen(p)
    assert sc.testcases[0].result.chrome.note == "validate sai"
    out = tmp_path / "o.yaml"
    dump_screen(sc, out)
    sc2 = load_screen(out)
    assert sc2.testcases[0].result.chrome.note == "validate sai"
