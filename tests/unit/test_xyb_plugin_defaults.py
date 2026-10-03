"""FR-1.5: which bundled plugins start enabled on a patient-facing install.

Upstream turns every bundled plugin on. That is the right default for a general
assistant and the wrong one for a patient managing a cancer diagnosis, so a
plugin opts out by declaring ``default_enabled: false`` in its ``plugin.yaml``.

An explicit user choice always wins: this only decides the state when
``config.json`` says nothing about the plugin.
"""

from __future__ import annotations

import pytest

from octop.infra.agents.plugins.bundled import default_bundled_plugins_root
from octop.infra.agents.plugins.manager import (
    PluginManifest,
    _bundled_default_enabled,
    _plugin_is_enabled,
    _read_plugin_yaml,
)

#: Not for a patient-facing install: games, horoscopes, gossip, memes, and the
#: media/lifestyle feeds that come with the general-purpose product.
EXPECTED_OFF: tuple[str, ...] = (
    "tetris",
    "fun-facts",
    "sports-scores",
    "bilibili-anime",
    "market-quotes",
    "hot-topics",
    "meme-maker",
    "movie-search",
    "daily-english",
    "fortune",
    "travel-inspire",
    "what-to-eat",
)

#: Genuinely useful to a patient or carer: keep them on.
EXPECTED_ON: tuple[str, ...] = (
    "weather",
    "pomodoro",
    "qrcode",
    "unit-convert",
    "wiki-summary",
    "server-status",
    "air-quality",
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """The resolver memoises per plugin id; tests must not share that cache."""
    _bundled_default_enabled.cache_clear()


def test_entertainment_plugins_are_off_by_default() -> None:
    assert _bundled_default_enabled.cache_info().currsize == 0
    for plugin_id in EXPECTED_OFF:
        assert _bundled_default_enabled(plugin_id) is False, (
            f"{plugin_id} would be enabled on a fresh patient-facing install"
        )


def test_practical_plugins_stay_on_by_default() -> None:
    for plugin_id in EXPECTED_ON:
        assert _bundled_default_enabled(plugin_id) is True, (
            f"{plugin_id} should still default to enabled"
        )


def test_unknown_plugin_falls_back_to_enabled() -> None:
    """A third-party or user-installed plugin keeps the upstream default."""
    assert _bundled_default_enabled("definitely-not-a-bundled-plugin") is True


def test_explicit_user_choice_beats_the_default() -> None:
    """Someone who turned a plugin on must keep it on."""
    assert _plugin_is_enabled({"tetris": True}, "tetris") is True
    assert _plugin_is_enabled({"weather": False}, "weather") is False
    # No entry in config -> fall back to the declared default.
    assert _plugin_is_enabled({}, "tetris") is False
    assert _plugin_is_enabled({}, "weather") is True


def test_the_opt_out_key_is_additive_for_the_harness() -> None:
    """The harness must still load the manifest with the extra key present.

    ``default_enabled`` is not part of the harness schema; it ignores unknown
    keys, which is what keeps this change upstream-safe.
    """
    root = default_bundled_plugins_root()
    for plugin_id in EXPECTED_OFF:
        manifest = PluginManifest.load(root / plugin_id / "plugin.yaml")
        assert manifest.id == plugin_id
        assert manifest.version


def test_every_opt_out_is_explicit_in_the_manifest() -> None:
    """The opt-out must be declared in the file, not inferred from its name."""
    root = default_bundled_plugins_root()
    for plugin_id in EXPECTED_OFF:
        data = _read_plugin_yaml(root / plugin_id)
        assert data.get("default_enabled") is False, (
            f"{plugin_id}/plugin.yaml lacks an explicit default_enabled: false"
        )


def test_no_unrelated_plugin_was_opted_out() -> None:
    """Only the curated list is off; a stray edit elsewhere would surprise users."""
    root = default_bundled_plugins_root()
    opted_out = set()
    for plugin_dir in sorted(root.iterdir()):
        if not (plugin_dir / "plugin.yaml").is_file():
            continue
        if _read_plugin_yaml(plugin_dir).get("default_enabled") is False:
            opted_out.add(plugin_dir.name)
    assert opted_out == set(EXPECTED_OFF)


def test_plugin_manifests_are_still_valid_yaml() -> None:
    root = default_bundled_plugins_root()
    for plugin_dir in sorted(root.iterdir()):
        path = plugin_dir / "plugin.yaml"
        if path.is_file():
            assert isinstance(_read_plugin_yaml(plugin_dir), dict), path
