"""The release archive must be accepted by the Claude app's skill upload."""
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_zip_layout(tmp_path):
    out = tmp_path / "google-trends.zip"
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_skill_zip.py"), str(out)], cwd=ROOT, check=True)
    names = zipfile.ZipFile(out).namelist()
    assert "google-trends/SKILL.md" in names
    assert all(n.startswith("google-trends/") for n in names)
    assert not any(".claude-plugin" in n or n.startswith("google-trends/tests") or "__pycache__" in n for n in names)
    assert "google-trends/scripts/trends_cli.py" in names
