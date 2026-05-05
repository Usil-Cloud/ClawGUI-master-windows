"""Regression guard for the GROUNDING_PROMPT brace-escape rule.

The wrapper template in scripts/dev/run_gui_owl.py is rendered with
str.format(user_prompt=...). The schema example inside it contains literal
JSON braces, which must be doubled ('{{' and '}}') so format() emits a
single brace and does not look up the JSON keys as format-spec keys.

If a future edit forgets to double-brace, str.format() raises KeyError
on the first un-escaped '{...}' it scans (e.g. KeyError: '\\n  "elements"'),
which manifests as HTTP 500 on every /analyze call -- silent on the unit
tests but loud at runtime. This test fails loudly at CI time instead.

Convention reference: phone_agent/config/prompts_guiowl.py uses the same
escape rule for its tool-call schema example.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
RUN_GUI_OWL_PATH = PROJECT_ROOT / "scripts" / "dev" / "run_gui_owl.py"
SETUP_PERCEPTION_PATH = PROJECT_ROOT / "scripts" / "dev" / "setup_perception_env.py"


def _load_run_gui_owl_module():
    """Load run_gui_owl.py without triggering its venv re-exec or model
    imports. The module-level body only imports `setup_perception_env`
    (for TIER_REPOS / _model_dir_for) -- everything else is lazy. We
    stub that one dependency, put scripts/dev on sys.path, and import.
    """
    sys.path.insert(0, str(SETUP_PERCEPTION_PATH.parent))
    if "setup_perception_env" not in sys.modules:
        stub = types.ModuleType("setup_perception_env")
        stub.TIER_REPOS = {"2b": "stub", "7b": "stub"}
        stub._model_dir_for = lambda tier: pathlib.Path("/nonexistent")
        sys.modules["setup_perception_env"] = stub

    spec = importlib.util.spec_from_file_location(
        "run_gui_owl_under_test", str(RUN_GUI_OWL_PATH),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_grounding_prompt_format_does_not_raise():
    """The whole point of this file: .format() must succeed."""
    mod = _load_run_gui_owl_module()
    rendered = mod.GROUNDING_PROMPT.format(user_prompt="describe the screen")
    assert isinstance(rendered, str) and rendered


def test_grounding_prompt_emits_literal_json_braces():
    mod = _load_run_gui_owl_module()
    rendered = mod.GROUNDING_PROMPT.format(user_prompt="x")
    # The schema example must reach the model with single braces, not doubled.
    assert '{\n  "elements"' in rendered, (
        "JSON schema example lost its opening brace -- check that the "
        "double-brace escape didn't get mangled."
    )
    assert "{{" not in rendered and "}}" not in rendered, (
        "doubled braces leaked into the rendered prompt -- the template "
        "should have exactly one un-escaped placeholder ({user_prompt})."
    )


def test_grounding_prompt_interpolates_user_prompt():
    mod = _load_run_gui_owl_module()
    sentinel = "SENTINEL_USER_PROMPT_XYZ_123"
    rendered = mod.GROUNDING_PROMPT.format(user_prompt=sentinel)
    assert sentinel in rendered


def test_grounding_prompt_has_exactly_one_format_field():
    """Guard against new placeholders sneaking in. If someone adds a
    second {field}, .format() will need a corresponding kwarg at the
    call site, and the call sites here pass only user_prompt."""
    import string
    mod = _load_run_gui_owl_module()
    fields = {
        name for _, name, _, _ in string.Formatter().parse(mod.GROUNDING_PROMPT)
        if name
    }
    assert fields == {"user_prompt"}, (
        f"GROUNDING_PROMPT must declare exactly one placeholder "
        f"('user_prompt'); found {fields}. If you added a new field, "
        f"update both call sites in run_gui_owl.py and this test."
    )
