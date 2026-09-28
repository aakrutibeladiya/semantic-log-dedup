from pathlib import Path

from sift.io import load_lines

FIXTURE = Path(__file__).parent / "fixtures" / "sample.log"


def test_load_lines_strips_newlines_and_keeps_original_index():
    lines = load_lines(FIXTURE)

    assert len(lines) == 5
    assert lines[0] == (0, "Invalid user admin from 173.234.31.186")
    assert lines[4] == (4, "Accepted password for bob from 10.0.0.9 port 22 ssh2")
    assert all(not text.endswith("\n") for _, text in lines)
