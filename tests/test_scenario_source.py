from pathlib import Path

from seers_harness.validation.scenario_source import (
    build_scratch_csv,
    default_request_ids,
)


def test_build_scratch_csv_captures_duplicate_rows_for_chosen_requests(tmp_path: Path):
    source = tmp_path / "raw.csv"
    source.write_text(
        "request_id#item_id#item_cat3_name\n"
        "r1#a#牙膏\n"
        "r2#b#牙膏\n"
        "r1#c#牙膏\n"
        "r3#d#牙膏\n",
        encoding="utf-8",
    )
    scratch = tmp_path / "scratch.csv"

    chosen = build_scratch_csv(source, scratch, 2)

    assert chosen == ["r1", "r2"]
    assert scratch.read_text(encoding="utf-8").splitlines() == [
        "request_id#item_id#item_cat3_name",
        "r1#a#牙膏",
        "r2#b#牙膏",
        "r1#c#牙膏",
    ]


def test_default_request_ids_reads_first_unique_ids(tmp_path: Path):
    source = tmp_path / "raw.csv"
    source.write_text(
        "request_id,item_id,item_cat3_name\n"
        "r1,a,牙膏\n"
        "r2,b,牙膏\n"
        "r1,c,牙膏\n",
        encoding="utf-8",
    )

    assert default_request_ids(csv=source, num_requests=2) == ["r1", "r2"]
