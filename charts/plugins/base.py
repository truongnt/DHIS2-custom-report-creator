"""
Base classes and shared constants for the chart plugin system.

Each chart type is a ChartPlugin subclass living in its own module under
charts/plugins/. The __init__.py of this package populates PLUGIN_REGISTRY
and the FIXED_TEMPLATES list consumed by the rest of the app.

de_type values (for reference):
  tracker_option  — tracker DE with option set (Case B)
  tracker_numeric — tracker DE without option set (Case C: aggregationType=SUM)
  aggregate       — aggregate data element (/api/analytics.json)
  indicator       — indicator (/api/analytics.json, same as aggregate)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

# ── Shared constants ──────────────────────────────────────────────────────────

AGG_TYPES: list[str] = ["SUM", "COUNT", "AVERAGE", "MIN", "MAX"]

TIME_GRAINS: list[str] = ["Monthly", "Quarterly", "Yearly"]

# Must match the PALETTE used in _SHARED_SCRIPT inside fixed_templates.py
PALETTE: list[str] = [
    "#e74c3c",
    "#3498db",
    "#f39c12",
    "#27ae60",
    "#9b59b6",
    "#1abc9c",
    "#e67e22",
    "#2980b9",
    "#8e44ad",
    "#16a085",
]


# ── Control dataclasses ───────────────────────────────────────────────────────

@dataclass
class MetricControl:
    """Describes a numeric / aggregate metric slot in a chart plugin."""
    id: str
    label: str
    max_count: int = 1
    allowed_types: tuple[str, ...] = ("tracker_numeric", "aggregate", "indicator")
    default_agg: str = "SUM"
    show_agg_picker: bool = True
    required: bool = True


@dataclass
class DimensionControl:
    """Describes a dimension (split-by) slot in a chart plugin.
    Any DE type can be a dimension; option-set DEs produce legend labels
    from their option values via DHIS2 metaData.items.

    max_count > 1 + show_alias=True make the picker behave like the metrics picker
    (multi-select DE/PA, each with an optional display alias) — used by the data table
    to disaggregate rows by one or more dimensions.
    """
    id: str
    label: str
    dimension_type: str = "category"
    allowed_types: tuple[str, ...] = ("tracker_option", "tracker_numeric", "aggregate", "indicator")
    required: bool = False
    hint: str = ""
    max_count: int = 1
    show_alias: bool = False


@dataclass
class SelectControl:
    """A fixed-choice control rendered as a SegmentedButton in the UI."""
    id: str
    label: str
    choices: tuple[str, ...]
    default: str = ""


@dataclass
class CheckboxGroupControl:
    """Multi-select control rendered as toggle buttons — any subset can be active.

    Value stored in plugin_options as comma-separated selected labels, e.g. "Level 2,Level 4".
    """
    id: str
    label: str
    choices: tuple[str, ...]
    default: tuple[str, ...] = ()  # initially checked items


@dataclass
class TextAreaControl:
    """A large multi-line text input (rendered as a tall monospace editor in the UI).

    Used for free-form content like the Custom HTML widget's HTML/JS template.
    Value stored in plugin_options as a plain string.
    """
    id: str
    label: str
    default: str = ""
    placeholder: str = ""
    height: int = 240
    monospace: bool = True


@dataclass
class TimeGrainControl:
    """Describes the time-grain selector for a chart plugin."""
    id: str = "time_grain"
    label: str = "Time grain"
    grains: tuple[str, ...] = ("Monthly", "Quarterly", "Yearly")
    default: str = "Monthly"


# ── Plugin base class ─────────────────────────────────────────────────────────

class ChartPlugin:
    """
    Abstract base for all chart plugins.

    Subclasses MUST set at minimum:
        id          — unique slug, e.g. "bar_monthly"
        label       — human-readable name shown in the template picker
        icon        — emoji or short string for the picker list
        description — one-sentence description
        preview_id  — key used by preview_canvas.py to draw the sample chart

    Subclasses SHOULD override:
        metrics     — list[MetricControl]
        dimensions  — list[DimensionControl]
        time_grain  — TimeGrainControl | None
        build_js()  — returns the per-card JS string
    """

    # ── Class-level declarations (set by each plugin subclass) ────────────────
    id: ClassVar[str] = ""
    label: ClassVar[str] = ""
    icon: ClassVar[str] = "📊"
    description: ClassVar[str] = ""
    preview_id: ClassVar[str] = ""
    hidden: ClassVar[bool] = False  # True = keep in registry for compat, hide from picker

    metrics: ClassVar[list[MetricControl]] = [
        MetricControl(id="metric", label="Data source")
    ]
    dimensions: ClassVar[list[DimensionControl]] = []
    options: ClassVar[list[SelectControl]] = []  # fixed-choice controls (SelectControl)
    time_grain: ClassVar[TimeGrainControl | None] = TimeGrainControl()

    # ── Class methods ─────────────────────────────────────────────────────────

    @classmethod
    def allowed_source_types(cls) -> set[str]:
        """
        Returns the union of allowed_types across all MetricControl and
        DimensionControl slots. Used to filter the DE picker in the UI.
        """
        types: set[str] = set()
        for m in cls.metrics:
            types.update(m.allowed_types)
        for d in cls.dimensions:
            types.update(d.allowed_types)
        return types

    # ── Shared JS/URL helpers (available to all subclasses) ──────────────────

    @classmethod
    def _filter_params(cls, config: dict) -> str:
        """Build &filter=... params from config["dimensions"]["filters"] list."""
        dims = config.get("dimensions") or {}
        stage = (config.get("source") or {}).get("stage_uid", "")
        out = []
        for f in dims.get("filters", []):
            de_uid = f.get("de_uid", "")
            op     = f.get("op", "EQ")
            val    = f.get("value", "")
            if not de_uid or not val:
                continue
            # Program attributes (TEA) are dimensioned by their bare uid, not stage.uid.
            prefix = "" if f.get("is_tea") else (f"{stage}." if stage else "")
            out.append(f"filter={prefix}{de_uid}:{op}:{val}")
        return "&".join(out)

    @classmethod
    def _group_by_params(cls, config: dict) -> str:
        """Build &dimension=... params from config["dimensions"]["group_by"] list."""
        dims = config.get("dimensions") or {}
        stage = (config.get("source") or {}).get("stage_uid", "")
        out = []
        for g in dims.get("group_by", []):
            de_uid = g.get("uid", "")
            if not de_uid:
                continue
            prefix = "" if g.get("is_tea") else (f"{stage}." if stage else "")
            out.append(f"dimension={prefix}{de_uid}")
        return "&".join(out)

    @classmethod
    def _extra_params(cls, config: dict) -> str:
        """Combine filter + group_by params with leading & if non-empty."""
        parts = [p for p in [cls._group_by_params(config), cls._filter_params(config)] if p]
        return ("&" + "&".join(parts)) if parts else ""

    @classmethod
    def _sort_limit_js(cls, config: dict, arr: str = "combined") -> str:
        """Return JS lines to sort and/or limit an array of {l, v} objects in-place.
        sort_by="None" skips sorting (keeps natural API order, e.g. chronological).
        """
        dims   = config.get("dimensions") or {}
        limit  = dims.get("row_limit", 0)
        by     = dims.get("sort_by", "None")
        dirn   = dims.get("sort_dir", "Asc")
        mult   = -1 if dirn == "Desc" else 1
        lines  = []
        if by == "Value":
            lines.append(f"  {arr}.sort((a,b) => ({mult}) * (a.v - b.v));")
        elif by == "Label":
            lines.append(f"  {arr}.sort((a,b) => ({mult}) * a.l.localeCompare(b.l));")
        # by == "None": no sort
        if limit and int(limit) > 0:
            lines.append(f"  if ({arr}.length > {limit}) {arr} = {arr}.slice(0, {limit});")
        return "\n".join(lines) if lines else ""

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        """
        Generate the per-card JavaScript string for card index n.

        Parameters
        ----------
        n      : card index (used for unique JS function/variable names)
        config : serialised card config dict, same shape as old
                 fixed_templates config dicts. Expected keys vary by plugin;
                 at minimum "plugin_id" and "metrics" (list of metric dicts).

        Returns
        -------
        str — JavaScript source that defines renderChart{n}Sample,
              renderChart{n}Real, and initChart{n}.

        Raises
        ------
        NotImplementedError if the subclass has not implemented this method.
        """
        raise NotImplementedError(
            f"ChartPlugin subclass '{cls.id}' must implement build_js()"
        )

    @classmethod
    def as_template_dict(cls) -> dict:
        """
        Return a dict compatible with the FIXED_TEMPLATES list consumed by
        the rest of the app (template picker, card builder, etc.).

        The dict has the same shape as the old hand-written FIXED_TEMPLATES
        entries, plus a "plugin" key pointing back to the class itself so
        callers can invoke build_js() directly.
        """
        return {
            "id": cls.id,
            "label": cls.label,
            "icon": cls.icon,
            "description": cls.description,
            "preview_id": cls.preview_id,
            "for_types": cls.allowed_source_types(),
            "plugin": cls,
        }


# ── Migration helper ──────────────────────────────────────────────────────────

# Maps old template IDs (used in saved card configs) to new plugin IDs.
_OLD_TO_NEW_ID: dict[str, str] = {
    "ft_bar_monthly":      "bar_monthly",
    "ft_line_trend":       "line_trend",
    "ft_stacked_cat":      "stacked_cat",
    "ft_pie_cat":          "pie_cat",
    "ft_bar_ou":           "bar_ou",
    "ft_scorecard":        "scorecard",
    "ft_line_multi":       "line_multi",
    "ft_grouped_bar":      "grouped_bar",
    "ft_combined_bar_line": "combined_bar_line",
}


def migrate_old_config(old: dict) -> dict:
    """
    Convert a card config dict that was saved with the old fixed_templates
    format (keys: template_id, de_uid, de_type, prog_uid, stage_uid, …)
    into the new plugin format (keys: plugin_id, metrics, dimensions).

    If the config already uses the new format (has "plugin_id"), it is
    returned unchanged.

    Parameters
    ----------
    old : dict — old-format card config as loaded from disk / session state.

    Returns
    -------
    dict — new-format config ready for use with ChartPlugin.build_js().
    """
    if "plugin_id" in old:
        # Already new format — nothing to do.
        return dict(old)

    new: dict = dict(old)

    # Translate template_id -> plugin_id
    old_tid = old.get("template_id", "")
    new["plugin_id"] = _OLD_TO_NEW_ID.get(old_tid, old_tid)
    new.pop("template_id", None)

    # Wrap the single DE info into a metrics list (unless multi-DE sources
    # are already present as de_sources, in which case convert those).
    de_sources = old.get("de_sources")
    if de_sources:
        # Multi-DE old format
        new["metrics"] = [
            {
                "uid": s.get("uid") or s.get("de_uid", ""),
                "name": s.get("name", ""),
                "type": s.get("type") or s.get("de_type", "aggregate"),
                "agg": s.get("agg", "SUM"),
                "prog_uid": s.get("prog_uid", ""),
                "stage_uid": s.get("stage_uid", ""),
            }
            for s in de_sources
        ]
        new.pop("de_sources", None)
    elif "de_uid" in old:
        # Single-DE old format
        new["metrics"] = [
            {
                "uid": old.get("de_uid", ""),
                "name": old.get("de_name", ""),
                "type": old.get("de_type", "aggregate"),
                "agg": old.get("agg_type", "SUM"),
                "prog_uid": old.get("prog_uid", ""),
                "stage_uid": old.get("stage_uid", ""),
            }
        ]
        new.pop("de_uid", None)
        new.pop("de_name", None)
        new.pop("de_type", None)
        new.pop("agg_type", None)
        new.pop("prog_uid", None)
        new.pop("stage_uid", None)

    # Wrap category DE (tracker_option) into dimensions list if present
    cat_uid = old.get("cat_uid") or old.get("category_uid", "")
    if cat_uid:
        new.setdefault("dimensions", [])
        new["dimensions"].append(
            {
                "id": "category",
                "uid": cat_uid,
                "name": old.get("cat_name", ""),
                "type": "tracker_option",
            }
        )
        new.pop("cat_uid", None)
        new.pop("category_uid", None)
        new.pop("cat_name", None)

    return new
