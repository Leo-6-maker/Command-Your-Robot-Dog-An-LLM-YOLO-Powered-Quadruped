"""Regression tests for immutable Task 4 benchmark batches."""

import json

import pytest

from run_task4_benchmark import build_manifest, prepare_output_root


def test_manifest_pins_revision_and_all_ten_trials():
    manifest = build_manifest("abc123")

    assert manifest["code_revision"] == "abc123"
    assert manifest["timeout_wall_s"] == 120
    assert len(manifest["trials"]) == 10
    assert len({trial["id"] for trial in manifest["trials"]}) == 10


def test_benchmark_output_directory_is_immutable(tmp_path):
    output = tmp_path / "new_batch"
    manifest = build_manifest("first-revision")
    prepare_output_root(output, manifest)

    manifest_path = output / "manifest.json"
    original = manifest_path.read_bytes()
    assert json.loads(original)["code_revision"] == "first-revision"

    with pytest.raises(FileExistsError, match="choose a new path"):
        prepare_output_root(output, build_manifest("different-revision"))

    assert manifest_path.read_bytes() == original
