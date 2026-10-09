import runpy
import zipfile
from pathlib import Path
from types import SimpleNamespace


def tool(name):
    return runpy.run_path(str(Path(__file__).parents[1] / "scripts" / name))


def test_metadata_inventory_distinguishes_aliases_from_candidate_copies(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "model.bin").write_bytes(b"abcd")
    (second / "model.bin").write_bytes(b"efgh")
    (first / "alias.bin").symlink_to(first / "model.bin")
    result = tool("inventory_weights.py")["inventory"]({"one": first, "two": second})
    assert len(result["same_file_aliases"]) == 1
    assert len(result["same_name_size_candidates"]) == 1
    assert all(row["content_sha256"] is None for row in result["files"])
    assert not result["deletion_authorized"]
    assert (second / "model.bin").read_bytes() == b"efgh"
    hashed = tool("inventory_weights.py")["inventory"]({"one": first, "two": second}, hash_contents=True)
    assert len(hashed["same_content_sha256"]) == 1
    assert all(row["content_sha256"] for row in hashed["files"])


def test_boundary_gate_counts_collection_skips_and_setup_failures():
    results = tool("installed_boundary_results.py")["Results"]()
    results.pytest_collectreport(SimpleNamespace(skipped=True, failed=False))
    results.pytest_runtest_logreport(SimpleNamespace(skipped=False, failed=True, when="setup", passed=False))
    assert results.skipped == 1 and results.failed == 1 and results.passed == 0


def test_weight_inventory_does_not_count_typescript_as_torchscript(tmp_path):
    (tmp_path / "index.ts").write_text("export const example = true;")
    with zipfile.ZipFile(tmp_path / "rave.ts", "w") as archive:
        archive.writestr("archive/data.pkl", b"fixture; never unpickle")
        archive.writestr("archive/constants.pkl", b"fixture; never unpickle")
    result = tool("inventory_weights.py")["inventory"]({"selected": tmp_path})
    assert [row["ref"] for row in result["files"]] == ["selected/rave.ts"]
    assert result["excluded_nonweight_files"][0]["ref"] == "selected/index.ts"
