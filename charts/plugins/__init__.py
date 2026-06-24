"""
Chart plugin registry.

Importing this package populates PLUGIN_REGISTRY and FIXED_TEMPLATES.
Individual plugin modules are imported with try/except so a partially-
implemented plugin set never breaks the rest of the app.

Usage
-----
    from charts.plugins import get_plugin, all_plugins, FIXED_TEMPLATES

    # Retrieve a plugin class by its ID
    cls = get_plugin("bar_monthly")
    js  = cls.build_js(n=0, config=card_config)

    # Iterate all registered plugins in display order
    for plugin in all_plugins():
        print(plugin.id, plugin.label)

    # Drop-in replacement for the old FIXED_TEMPLATES list
    templates = FIXED_TEMPLATES   # list[dict] with same keys as before
"""
from __future__ import annotations

from charts.plugins.base import ChartPlugin  # noqa: F401 — re-exported for convenience

# ── Plugin imports ────────────────────────────────────────────────────────────

# Unified bar (replaces bar_monthly + stacked_cat + grouped_bar + bar_ou)
try:
    from charts.plugins.bar import BarPlugin
except Exception:  # noqa: BLE001
    BarPlugin = None  # type: ignore[assignment,misc]

# Legacy bar plugins — kept for backward compat, hidden from picker
try:
    from charts.plugins.bar_monthly import BarMonthlyPlugin
except Exception:  # noqa: BLE001
    BarMonthlyPlugin = None  # type: ignore[assignment,misc]

try:
    from charts.plugins.line_trend import LineTrendPlugin
except Exception:  # noqa: BLE001
    LineTrendPlugin = None  # type: ignore[assignment,misc]

try:
    from charts.plugins.stacked_cat import StackedCatPlugin
except Exception:  # noqa: BLE001
    StackedCatPlugin = None  # type: ignore[assignment,misc]

try:
    from charts.plugins.pie_cat import PieCatPlugin
except Exception:  # noqa: BLE001
    PieCatPlugin = None  # type: ignore[assignment,misc]

try:
    from charts.plugins.bar_ou import BarOuPlugin
except Exception:  # noqa: BLE001
    BarOuPlugin = None  # type: ignore[assignment,misc]

try:
    from charts.plugins.scorecard import ScorecardPlugin
except Exception:  # noqa: BLE001
    ScorecardPlugin = None  # type: ignore[assignment,misc]

# Multi-DE plugins
try:
    from charts.plugins.line_multi import LineMultiPlugin
except Exception:  # noqa: BLE001
    LineMultiPlugin = None  # type: ignore[assignment,misc]

try:
    from charts.plugins.grouped_bar import GroupedBarPlugin
except Exception:  # noqa: BLE001
    GroupedBarPlugin = None  # type: ignore[assignment,misc]

try:
    from charts.plugins.combined_bar_line import CombinedBarLinePlugin
except Exception:  # noqa: BLE001
    CombinedBarLinePlugin = None  # type: ignore[assignment,misc]

try:
    from charts.plugins.table_view import TablePlugin
except Exception:  # noqa: BLE001
    TablePlugin = None  # type: ignore[assignment,misc]


# ── Registry ──────────────────────────────────────────────────────────────────

# Ordered list of (plugin_id, class_or_None) in the intended display order.
# None entries are filtered out — they represent not-yet-implemented plugins.
_ORDERED: list[tuple[str, type[ChartPlugin] | None]] = [
    # ── Visible plugins (shown in picker) ──
    ("bar",               BarPlugin),
    ("line_trend",        LineTrendPlugin),
    ("line_multi",        LineMultiPlugin),
    ("pie_cat",           PieCatPlugin),
    ("scorecard",         ScorecardPlugin),
    ("combined_bar_line", CombinedBarLinePlugin),
    ("table_view",        TablePlugin),
    # ── Hidden legacy plugins (backward compat only) ──
    ("bar_monthly",       BarMonthlyPlugin),
    ("stacked_cat",       StackedCatPlugin),
    ("grouped_bar",       GroupedBarPlugin),
    ("bar_ou",            BarOuPlugin),
]

PLUGIN_REGISTRY: dict[str, type[ChartPlugin]] = {
    plugin_id: cls
    for plugin_id, cls in _ORDERED
    if cls is not None
}


# ── Public accessors ──────────────────────────────────────────────────────────

def get_plugin(plugin_id: str) -> type[ChartPlugin]:
    """
    Return the ChartPlugin subclass registered under plugin_id.

    Raises
    ------
    KeyError — if no plugin with that ID is registered (either unknown ID or
               the plugin module failed to import).
    """
    try:
        return PLUGIN_REGISTRY[plugin_id]
    except KeyError:
        registered = ", ".join(sorted(PLUGIN_REGISTRY)) or "(none)"
        raise KeyError(
            f"No chart plugin registered with id={plugin_id!r}. "
            f"Registered plugins: {registered}"
        ) from None


def all_plugins() -> list[type[ChartPlugin]]:
    """Return ALL registered plugins (including hidden) in display order."""
    return [cls for _, cls in _ORDERED if cls is not None]


def visible_plugins() -> list[type[ChartPlugin]]:
    """Return only non-hidden plugins for the template picker UI."""
    return [cls for cls in all_plugins() if not cls.hidden]


# ── FIXED_TEMPLATES (drop-in replacement for the old list) ───────────────────
# Includes hidden plugins so backward-compat lookups still work.

FIXED_TEMPLATES: list[dict] = [p.as_template_dict() for p in all_plugins()]
