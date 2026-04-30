"""GUI-Owl (Mobile-Agent v3) inference adapter.

Sends a Screenshot to a GUI-Owl /analyze endpoint over HTTP and normalizes the
response to a ScreenState. The ONLY GUI-Owl-aware module in the project — every
other module consumes ScreenState/UIElement from phone_agent.perception.types
and stays model-agnostic. Tier selection is config-driven; the wire format is
documented in docs/INTEGRATION_CONTRACT.md.
"""
# Notes: docs/phone_agent/perception/gui_owl_adapter.md
from __future__ import annotations

import base64
import logging
import subprocess
from typing import Any

import requests

from phone_agent.config.endpoints import GUI_OWL_TIERS, resolve_gui_owl_endpoint
from phone_agent.perception.types import ScreenState, UIElement
from phone_agent.windows.screenshot import Screenshot

log = logging.getLogger(__name__)

_VRAM_TIER_THRESHOLDS_MIB = (
    (8 * 1024,  "2b"),
    (24 * 1024, "7b"),
    (80 * 1024, "72b"),
)
_TOP_TIER = "235b"
# When nvidia-smi is missing, assume "no discrete NVIDIA GPU" and pick the
# laptop-class tier. P1/P2 users with real NVIDIA hardware hit the detect path
# proper; this fallback only fires for the P3 / consumer-laptop case.
_DEFAULT_TIER_ON_DETECT_FAIL = "2b"


def _detect_tier_from_vram() -> str:
    """Pick a tier from `nvidia-smi` free-VRAM. Falls back to '2b' if unavailable.

    The '2b' fallback assumes that a missing nvidia-smi means "no discrete
    NVIDIA GPU" — typical for consumer laptops (the P3 persona). P1/P2 users
    with real NVIDIA hardware reach the detect path proper and get sized to
    their actual free VRAM.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5.0, check=True,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError) as e:
        log.warning(
            "GUI-Owl tier auto-detect: nvidia-smi unavailable (%s); defaulting to %r",
            e, _DEFAULT_TIER_ON_DETECT_FAIL,
        )
        return _DEFAULT_TIER_ON_DETECT_FAIL

    free_values_mib: list[int] = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            free_values_mib.append(int(line))
        except ValueError:
            continue
    if not free_values_mib:
        log.warning(
            "GUI-Owl tier auto-detect: nvidia-smi output unparseable; defaulting to %r",
            _DEFAULT_TIER_ON_DETECT_FAIL,
        )
        return _DEFAULT_TIER_ON_DETECT_FAIL

    free_mib = max(free_values_mib)
    for threshold, tier in _VRAM_TIER_THRESHOLDS_MIB:
        if free_mib < threshold:
            return tier
    return _TOP_TIER


def _fallback_state(failed_step: str, error: str) -> ScreenState:
    log.warning("GUI-Owl analyze failed at step %r: %s", failed_step, error)
    return ScreenState(
        elements=(),
        planned_action="",
        reflection="",
        raw_response={"fallback": True, "failed_step": failed_step, "error": error},
    )


def _parse_element(item: dict[str, Any]) -> UIElement:
    bbox = tuple(item["bbox"])
    if len(bbox) != 4:
        raise ValueError(f"bbox must have 4 ints, got {bbox!r}")
    return UIElement(
        label=str(item["label"]),
        bbox=(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
        confidence=float(item.get("confidence", 0.0)),
        element_type=str(item.get("type", "other")),
    )


class GUIOwlAdapter:
    """HTTP adapter for a GUI-Owl /analyze endpoint.

    Parameters
    ----------
    model_tier
        ``'auto'`` (default — pick by free VRAM), or one of
        ``'2b' | '7b' | '72b' | '235b'``. Always overridable per-instance.
    endpoint_url
        Optional override for the resolved endpoint. If set, this URL is used
        verbatim regardless of tier-based config.
    request_timeout
        Per-request timeout in seconds.
    """

    def __init__(
        self,
        model_tier: str = "auto",
        endpoint_url: str | None = None,
        request_timeout: float = 30.0,
    ) -> None:
        if model_tier == "auto":
            model_tier = _detect_tier_from_vram()
        elif model_tier not in GUI_OWL_TIERS:
            raise ValueError(
                f"model_tier must be 'auto' or one of {GUI_OWL_TIERS}; got {model_tier!r}"
            )
        self.model_tier = model_tier
        self._endpoint_override = endpoint_url
        self.request_timeout = request_timeout
        log.info("GUIOwlAdapter initialized: tier=%s endpoint=%s",
                 self.model_tier, self._describe_endpoint())

    def _describe_endpoint(self) -> str:
        if self._endpoint_override:
            return self._endpoint_override
        try:
            return resolve_gui_owl_endpoint(self.model_tier)
        except KeyError:
            return "<unresolved>"

    def analyze(self, screenshot: Screenshot, prompt: str = "") -> ScreenState:
        try:
            endpoint = (
                self._endpoint_override
                if self._endpoint_override
                else resolve_gui_owl_endpoint(self.model_tier)
            )
            if not endpoint:
                return _fallback_state("resolve_endpoint", "endpoint resolved to empty string")
        except KeyError as e:
            return _fallback_state("resolve_endpoint", str(e))

        try:
            png_bytes = base64.b64decode(screenshot.base64_data)
        except (ValueError, TypeError) as e:
            return _fallback_state("resolve_endpoint", f"screenshot base64 decode failed: {e}")

        url = f"{endpoint}/analyze"
        files = {"image": ("screenshot.png", png_bytes, "image/png")}
        data = {"prompt": prompt, "tier": self.model_tier}

        try:
            response = requests.post(url, files=files, data=data, timeout=self.request_timeout)
        except requests.RequestException as e:
            return _fallback_state("connect", f"{type(e).__name__}: {e}")

        if response.status_code != 200:
            return _fallback_state(
                "http_status",
                f"HTTP {response.status_code}: {response.text[:200]}",
            )

        try:
            payload = response.json()
        except ValueError as e:
            return _fallback_state("parse_json", str(e))

        try:
            raw_elements = payload["elements"]
            planned_action = str(payload["planned_action"])
            reflection = str(payload.get("reflection", ""))
            elements = tuple(_parse_element(e) for e in raw_elements)
        except (KeyError, TypeError, ValueError) as e:
            return _fallback_state("parse_schema", f"{type(e).__name__}: {e}")

        return ScreenState(
            elements=elements,
            planned_action=planned_action,
            reflection=reflection,
            raw_response=payload,
        )
