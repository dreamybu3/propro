import subprocess
import sys


def test_module_entrypoint_preserves_failure_exit_code(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "gaplens", "repair", "--reference", str(tmp_path / "absent.csv"),
         "--input", str(tmp_path / "absent-input.csv"), "--output", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "does not exist" in result.stderr
    assert "Traceback" not in result.stderr
