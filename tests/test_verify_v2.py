"""Historical source hashes accept only explicit, connected corrections."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_v2", ROOT / "scripts/verify_v2.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


@pytest.fixture
def sources(tmp_path, monkeypatch):
    name = "src/gaplens/core.py"
    path = tmp_path / name
    path.parent.mkdir(parents=True)
    path.write_bytes(b"corrected source")
    hashes = {label: hashlib.sha256(content).hexdigest() for label, content in
              [("old", b"original source"), ("middle", b"first correction"),
               ("new", path.read_bytes()), ("other", b"unrelated source")]}
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    return tmp_path, name, hashes


def amendment(name, old, new):
    return {"path": name, "old_sha256": old, "new_sha256": new,
            "reason": "Correctness repair", "record": "docs/v2/CORRECTIONS.md",
            "first_holdout_already_inspected": True}


def manifest(root, name, current, changes):
    path = root / "configs/v2_freeze.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"protected_sha256": {name: current},
                               "validation_amendments": changes}))
    return path


def test_exact_source_hash_needs_no_manifest_or_git_checkout(sources):
    _, name, hashes = sources
    assert verifier.verify_source_hashes({name: hashes["new"]}) == []


def test_registered_correction_is_reported_without_rewriting_history(sources):
    root, name, hashes = sources
    change = amendment(name, hashes["old"], hashes["new"])
    freeze = manifest(root, name, hashes["new"], [change])
    run = root / "run.json"
    run.write_text(json.dumps({"code_sha256": {name: hashes["old"]}}))
    before = {p: p.read_bytes() for p in (run, freeze, root / name)}
    assert verifier.verify_source_hashes(json.loads(run.read_text())["code_sha256"]) == [change]
    assert all(p.read_bytes() == content for p, content in before.items())


def test_connected_chain_can_start_at_a_later_historical_checkpoint(sources):
    root, name, hashes = sources
    first = amendment(name, hashes["old"], hashes["middle"])
    second = amendment(name, hashes["middle"], hashes["new"])
    manifest(root, name, hashes["new"], [first, second])
    assert verifier.verify_source_hashes({name: hashes["old"]}) == [first, second]
    assert verifier.verify_source_hashes({name: hashes["middle"]}) == [second]


def test_changed_source_without_manifest_is_rejected(sources):
    _, name, hashes = sources
    with pytest.raises(ValueError, match="without an amendment manifest"):
        verifier.verify_source_hashes({name: hashes["old"]})


@pytest.mark.parametrize("fault", ["unregistered", "wrong_path", "wrong_start", "wrong_end",
                                  "wrong_protected", "broken_chain", "cycle", "ambiguous"])
def test_unregistered_or_broken_amendment_cannot_authorize_source_drift(sources, fault):
    root, name, h = sources
    changes = [amendment(name, h["old"], h["new"])]
    protected = h["new"]
    if fault == "unregistered":
        changes = []
    elif fault == "wrong_path":
        changes[0]["path"] = "src/gaplens/another_model.py"
    elif fault == "wrong_start":
        changes[0]["old_sha256"] = h["other"]
    elif fault == "wrong_end":
        changes[0]["new_sha256"] = h["other"]
    elif fault == "wrong_protected":
        protected = h["other"]
    elif fault == "broken_chain":
        changes = [amendment(name, h["old"], h["middle"]),
                   amendment(name, h["other"], h["new"])]
    elif fault == "cycle":
        changes = [amendment(name, h["old"], h["middle"]),
                   amendment(name, h["middle"], h["old"])]
    elif fault == "ambiguous":
        changes.append(amendment(name, h["old"], h["other"]))
    manifest(root, name, protected, changes)
    with pytest.raises(ValueError, match="[Nn]umerical source"):
        verifier.verify_source_hashes({name: h["old"]})
