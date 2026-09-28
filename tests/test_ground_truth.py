"""extract_username patterns and label joins, on tiny synthetic data (no dataset download needed)."""

import pandas as pd
import pytest
from eval.ground_truth import default_account_labels, extract_username, root_login_labels, template_labels


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("Invalid user webmaster from 173.234.31.186", "webmaster"),
        ("input_userauth_request: invalid user oracle [preauth]", "oracle"),
        ("Failed none for invalid user test from 1.2.3.4 port 22 ssh2", "test"),
        ("Failed password for invalid user guest from 1.2.3.4 port 22 ssh2", "guest"),
        ("Failed password for alice from 10.0.0.5 port 22 ssh2", "alice"),
        ("Accepted password for bob from 10.0.0.9 port 22 ssh2", "bob"),
        ("Disconnecting: Too many authentication failures for admin [preauth]", "admin"),
        ("pam_unix(sshd:session): session opened for user carol by (uid=0)", "carol"),
        ("pam_unix(sshd:session): session closed for user carol", "carol"),
        ("pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=1.2.3.4 user=root", "root"),
        ("message repeated 5 times: [ Failed password for root from 1.2.3.4 port 22]", "root"),
        ("Connection closed by 1.2.3.4 [preauth]", None),
        ("pam_unix(sshd:auth): check pass; user unknown", None),
    ],
)
def test_extract_username(content, expected):
    assert extract_username(content) == expected


def _structured(rows: list[tuple[int, str, str]]) -> pd.DataFrame:
    """`rows` is (LineId, EventId, Content)."""
    df = pd.DataFrame(rows, columns=["LineId", "EventId", "Content"])
    df.index = df["LineId"] - 1
    return df


def test_template_labels_joins_by_event_id(tmp_path):
    structured = _structured(
        [
            (1, "E13", "Invalid user admin from 1.2.3.4"),
            (2, "E1", "Accepted password for alice from 10.0.0.5 port 22 ssh2"),
        ]
    )
    labels_csv = tmp_path / "labels.csv"
    labels_csv.write_text("EventId,Q1,Q2\nE13,1,0\nE1,0,0\n")

    result = template_labels(structured, labels_csv, "Q1")

    assert result == {0: 1, 1: 0}


def test_default_account_labels_matches_listed_accounts_case_insensitively():
    structured = _structured(
        [
            (1, "E13", "Invalid user Admin from 1.2.3.4"),
            (2, "E13", "Invalid user jsmith from 5.6.7.8"),
            (3, "E1", "Accepted password for alice from 10.0.0.5 port 22 ssh2"),
        ]
    )

    result = default_account_labels(structured)

    assert result == {0: 1, 1: 0, 2: 0}


def test_root_login_labels_matches_only_root():
    structured = _structured(
        [
            (1, "E13", "Invalid user root from 1.2.3.4"),
            (2, "E13", "Invalid user admin from 5.6.7.8"),
        ]
    )

    result = root_login_labels(structured)

    assert result == {0: 1, 1: 0}
