from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OFFICE_HTML = PROJECT_ROOT / "app" / "web" / "index.html"


def test_agent_office_course_names_match_project_subjects() -> None:
    html = OFFICE_HTML.read_text(encoding="utf-8")
    config = yaml.safe_load((PROJECT_ROOT / "config" / "subjects.yaml").read_text(encoding="utf-8"))
    subject_names = {code: item["name"] for code, item in config["subjects"].items()}
    name_block = html.split("const officeCourseNames = {", 1)[1].split("};", 1)[0]
    office_names = dict(re.findall(r"^\s*([A-Z]+):'([^']+)'", name_block, flags=re.MULTILINE))
    assert office_names == subject_names


def test_workstation_name_is_drawn_once_per_home_worker() -> None:
    html = OFFICE_HTML.read_text(encoding="utf-8")
    pixel_worker = html.split("function drawPixelWorker", 1)[1].split("function hashOfficeText", 1)[
        0
    ]
    office_draw = html.split("function drawOffice(time)", 1)[1].split(
        "function startOfficeAnimation", 1
    )[0]
    assert pixel_worker.count("drawOfficeTag(ctx, title") == 1
    assert "pixelLabel(officeCtx, label" not in office_draw


@pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js is required for the Agent Office navigation test"
)
def test_agent_office_navigation_and_canvas_rendering() -> None:
    result = subprocess.run(
        [shutil.which("node") or "node", "tests/test_agent_office.js"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "225 routes" in result.stdout


@pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js is required for the web UI helper test"
)
def test_web_ui_job_and_settings_helpers() -> None:
    result = subprocess.run(
        [shutil.which("node") or "node", "tests/test_web_ui.js"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "UI_HELPERS_OK" in result.stdout
