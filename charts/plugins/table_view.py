"""
TablePlugin — tabular display with sort, filter, heatmap, and CSV download.

Modes
-----
aggregated : analytics API -> org unit rows x period columns (pivoted)
raw        : analytics API -> flat rows, one column per response header

plugin_options keys
-------------------
mode      : Aggregated | Raw
theme     : Default | Blue | Green | Light | Dark
heatmap   : Off | On
stripe    : Off | On
border    : Light | None | Dark
font_size : Medium | Small | Large
"""
from __future__ import annotations

import json as _json

from charts.plugins.base import ChartPlugin, MetricControl, SelectControl, TimeGrainControl

_THEMES: dict[str, dict[str, str]] = {
    "Default": {"header_bg": "#2c3e50", "header_fg": "#ffffff", "accent": "#3498db"},
    "Blue":    {"header_bg": "#1a5276", "header_fg": "#ffffff", "accent": "#2e86c1"},
    "Green":   {"header_bg": "#1e8449", "header_fg": "#ffffff", "accent": "#27ae60"},
    "Light":   {"header_bg": "#dfe6e9", "header_fg": "#2d3436", "accent": "#b2bec3"},
    "Dark":    {"header_bg": "#17202a", "header_fg": "#f2f3f4", "accent": "#566573"},
}

_SAMPLE_AGG_COLS = ["Org Unit", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
_SAMPLE_AGG_ROWS = [
    ["District A", "120", "145", "98",  "167", "203", "189"],
    ["District B", "45",  "67",  "89",  "123", "145", "167"],
    ["District C", "234", "198", "245", "267", "189", "212"],
    ["District D", "78",  "56",  "34",  "45",  "67",  "89"],
    ["District E", "156", "178", "189", "201", "212", "198"],
    ["District F", "310", "287", "298", "321", "267", "245"],
]

_SAMPLE_RAW_COLS = ["Facility", "Period", "Age", "Sex", "Cases"]
_SAMPLE_RAW_ROWS = [
    ["Clinic A",    "2024-01", "25", "Male",   "12"],
    ["Clinic B",    "2024-01", "34", "Female", "8"],
    ["Health Post", "2024-01", "18", "Male",   "3"],
    ["Clinic A",    "2024-02", "29", "Female", "15"],
    ["Clinic C",    "2024-02", "41", "Male",   "20"],
    ["Health Post", "2024-02", "22", "Female", "6"],
    ["Clinic B",    "2024-03", "55", "Male",   "9"],
    ["Clinic C",    "2024-03", "31", "Female", "18"],
]


def _po(po: dict, key: str, default):
    return po.get(key, default) if po else default


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ── JS helpers ─────────────────────────────────────────────────────────────────

def _helpers_js(n: int, po: dict) -> str:
    """Returns JS constants + render/mount functions for chart n."""
    theme_name = _po(po, "theme",     "Default")
    heatmap    = _po(po, "heatmap",   "Off") == "On"
    stripe     = _po(po, "stripe",    "On")  == "On"
    border_val = _po(po, "border",    "Light")
    font_size  = _po(po, "font_size", "Medium")

    theme  = _THEMES.get(theme_name, _THEMES["Default"])
    hdr_bg = theme["header_bg"]
    hdr_fg = theme["header_fg"]
    accent = theme["accent"]
    ar, ag, ab = _hex_to_rgb(accent)

    fs = {"Small": "11px", "Medium": "13px", "Large": "15px"}.get(font_size, "13px")
    border_css = {
        "None":  "",
        "Light": "border:1px solid #dee2e6;",
        "Dark":  "border:2px solid #343a40;",
    }.get(border_val, "border:1px solid #dee2e6;")
    stripe_odd  = "#f8f9fa" if stripe else "transparent"
    heatmap_js  = "true" if heatmap else "false"

    return f"""\
    const _T{n} = {{
      hdrBg:'{hdr_bg}', hdrFg:'{hdr_fg}',
      accentR:{ar}, accentG:{ag}, accentB:{ab},
      fs:'{fs}', border:'{border_css}', stripe:'{stripe_odd}',
      heatmap:{heatmap_js},
    }};
    let _tS{n} = {{ sc:-1, sd:1, fi:{{}} }};
    let _tD{n} = {{ cols:[], rows:[] }};

    function _tHeat{n}(v,mn,mx) {{
      if(mx<=mn) return '';
      const t=(v-mn)/(mx-mn);
      const r=Math.round(255+(_T{n}.accentR-255)*t);
      const g=Math.round(255+(_T{n}.accentG-255)*t);
      const b=Math.round(255+(_T{n}.accentB-255)*t);
      return `rgb(${{r}},${{g}},${{b}})`;
    }}

    function _tCSV{n}() {{
      const {{cols,rows}}=_tD{n};
      const e=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
      const txt=[cols.map(e).join(','),...rows.map(r=>r.map(e).join(','))].join('\\r\\n');
      const blob=new Blob(['\\ufeff'+txt],{{type:'text/csv;charset=utf-8'}});
      const a=Object.assign(document.createElement('a'),{{href:URL.createObjectURL(blob),download:'table.csv'}});
      document.body.appendChild(a);a.click();
      setTimeout(()=>{{URL.revokeObjectURL(a.href);a.remove();}},0);
    }}

    function _tRender{n}(wrap) {{
      const o=_T{n}, st=_tS{n};
      const {{cols,rows}}=_tD{n};
      const cm={{}},cx={{}};
      if(o.heatmap) {{
        cols.forEach((_,ci)=>{{
          const ns=rows.map(r=>parseFloat(r[ci])).filter(v=>!isNaN(v));
          if(ns.length){{cm[ci]=Math.min(...ns);cx[ci]=Math.max(...ns);}}
        }});
      }}
      let disp=rows.slice();
      if(st.sc>=0) {{
        disp.sort((a,b)=>{{
          const av=a[st.sc],bv=b[st.sc],an=parseFloat(av),bn=parseFloat(bv);
          return(!isNaN(an)&&!isNaN(bn)?an-bn:String(av).localeCompare(String(bv)))*st.sd;
        }});
      }}
      Object.entries(st.fi).forEach(([ci,fv])=>{{
        if(!fv)return;
        const lo=fv.toLowerCase();
        disp=disp.filter(r=>String(r[ci]??'').toLowerCase().includes(lo));
      }});

      const bd=o.border;
      const thS=`background:${{o.hdrBg}};color:${{o.hdrFg}};padding:5px 8px;font-size:${{o.fs}};cursor:pointer;white-space:nowrap;${{bd}}position:sticky;top:0;z-index:1;user-select:none;`;
      const tdS=`padding:4px 8px;font-size:${{o.fs}};${{bd}}`;
      const fS=`padding:2px 4px;background:#f5f5f5;${{bd}}`;

      let h=`<table style="width:100%;border-collapse:collapse;">`;
      h+='<thead><tr>'+cols.map((c,i)=>{{
        const arr=st.sc===i?(st.sd>0?' ▲':' ▼'):'';
        return `<th style="${{thS}}" data-sc="${{i}}">${{c}}${{arr}}</th>`;
      }}).join('')+'</tr>';
      h+='<tr>'+cols.map((_,i)=>{{
        const fv=st.fi[i]||'';
        return `<td style="${{fS}}"><input type="text" placeholder="🔍" value="${{fv}}" data-fi="${{i}}" style="width:100%;font-size:11px;border:1px solid #ccc;padding:2px 3px;box-sizing:border-box;background:white;"></td>`;
      }}).join('')+'</tr></thead><tbody>';
      disp.forEach((row,ri)=>{{
        const rb=(ri%2===1)?o.stripe:'transparent';
        h+=`<tr style="background:${{rb}}">`;
        row.forEach((cell,ci)=>{{
          let bg='';
          if(o.heatmap&&cm[ci]!==undefined){{
            const v=parseFloat(cell);
            if(!isNaN(v))bg=`background:${{_tHeat{n}(v,cm[ci],cx[ci])}};`;
          }}
          h+=`<td style="${{tdS}}${{bg}}">${{cell??''}}</td>`;
        }});
        h+='</tr>';
      }});
      h+='</tbody></table>';

      wrap.querySelector('[data-tb="{n}"]').innerHTML=h;
      wrap.querySelectorAll('th[data-sc]').forEach(th=>
        th.addEventListener('click',()=>{{
          const c=+th.dataset.sc;
          _tS{n}.sd=(_tS{n}.sc===c?-_tS{n}.sd:1);
          _tS{n}.sc=c;
          _tRender{n}(wrap);
        }})
      );
      wrap.querySelectorAll('input[data-fi]').forEach(inp=>
        inp.addEventListener('input',()=>{{
          _tS{n}.fi[inp.dataset.fi]=inp.value;
          _tRender{n}(wrap);
        }})
      );
    }}

    function _tMount{n}(cvs,cols,rows) {{
      cvs.style.display='none';
      const par=cvs.parentElement;
      let wrap=par.querySelector('[data-tw="{n}"]');
      if(!wrap){{
        wrap=document.createElement('div');
        wrap.setAttribute('data-tw','{n}');
        wrap.style.cssText='position:absolute;top:0;left:0;width:100%;height:100%;display:flex;flex-direction:column;background:white;';
        const bar=document.createElement('div');
        bar.style.cssText='padding:3px 6px;background:#f8f9fa;border-bottom:1px solid #dee2e6;flex-shrink:0;';
        bar.innerHTML='<button onclick="_tCSV{n}()" style="font-size:11px;padding:2px 8px;cursor:pointer;border:1px solid #aaa;background:white;border-radius:3px;">&#8595; Download CSV</button>';
        const body=document.createElement('div');
        body.setAttribute('data-tb','{n}');
        body.style.cssText='flex:1;overflow:auto;';
        wrap.appendChild(bar);
        wrap.appendChild(body);
        par.appendChild(wrap);
      }}
      _tD{n}={{cols,rows}};
      _tS{n}={{sc:-1,sd:1,fi:{{}}}};
      _tRender{n}(wrap);
    }}
"""


def _sample_js(n: int, po: dict) -> str:
    mode = _po(po, "mode", "Aggregated")
    cols = _SAMPLE_RAW_COLS if mode == "Raw" else _SAMPLE_AGG_COLS
    rows = _SAMPLE_RAW_ROWS if mode == "Raw" else _SAMPLE_AGG_ROWS
    cols_js = _json.dumps(cols)
    rows_js = _json.dumps(rows)
    return f"""\
    function renderChart{n}Sample(cvs) {{
      _tMount{n}(cvs, {cols_js}, {rows_js});
    }}"""


def _real_js(n: int, config: dict, po: dict) -> str:
    mode    = _po(po, "mode", "Aggregated")
    metrics = config.get("metrics", [])
    extra   = ChartPlugin._extra_params(config)
    dx_uids = ";".join(m["uid"] for m in metrics if m.get("uid"))

    if mode == "Raw":
        fetch_block = f"""\
            const d=await dhis2Get(
              'api/analytics.json?dimension=dx:{dx_uids}'
              +'&dimension=pe:'+encodeURIComponent(pe)
              +'&dimension=ou:'+encodeURIComponent(ou)
              +'&displayProperty=NAME{extra}'
            );
            const meta=d.metaData?.items||{{}};
            const cols=d.headers.map(h=>h.column);
            const rows=d.rows.map(r=>r.map((v,i)=>meta[v]?.name||v));
            _tMount{n}(cvs,cols,rows);"""
    else:
        fetch_block = f"""\
            const d=await dhis2Get(
              'api/analytics.json?dimension=dx:{dx_uids}'
              +'&dimension=pe:'+encodeURIComponent(pe)
              +'&dimension=ou:'+encodeURIComponent(ou)
              +'&displayProperty=NAME{extra}'
            );
            const meta=d.metaData?.items||{{}};
            const res=v=>meta[v]?.name||v;
            const dxI=d.headers.findIndex(h=>h.name==='dx');
            const ouI=d.headers.findIndex(h=>h.name==='ou');
            const peI=d.headers.findIndex(h=>h.name==='pe');
            const vI =d.headers.findIndex(h=>h.name==='value');
            const ous=[...new Set(d.rows.map(r=>r[ouI]))].sort();
            const dxs=[...new Set(d.rows.map(r=>r[dxI]))];
            const pes=[...new Set(d.rows.map(r=>r[peI]))].sort();
            const lkp={{}};
            d.rows.forEach(r=>{{ lkp[r[ouI]+':'+r[dxI]+':'+r[peI]]=r[vI]; }});
            const colKeys=[];
            const cols=['Org Unit'];
            dxs.forEach(dx=>pes.forEach(pe2=>{{
              cols.push(dxs.length>1?res(dx)+' '+formatPeriodLabel(pe2):formatPeriodLabel(pe2));
              colKeys.push({{dx,pe:pe2}});
            }}));
            const rows=ous.map(ou2=>[res(ou2),...colKeys.map(k=>lkp[ou2+':'+k.dx+':'+k.pe]||'')]);
            _tMount{n}(cvs,cols,rows);"""

    return f"""\
    async function initChart{n}(ou,pe) {{
      document.getElementById('loading{n}').style.display='none';
      const cvs=document.getElementById('chart{n}');
      cvs.style.display='block';
      if(PREVIEW){{ renderChart{n}Sample(cvs); return; }}
      document.getElementById('error{n}').style.display='none';
      try {{
        {fetch_block}
      }} catch(e) {{
        console.error('[Chart{n}]',e);
        document.getElementById('error{n}').textContent='Failed: '+e.message;
        document.getElementById('error{n}').style.display='block';
      }}
    }}"""


# ── Plugin class ───────────────────────────────────────────────────────────────

class TablePlugin(ChartPlugin):
    id          = "table_view"
    label       = "Data Table"
    icon        = "📋"
    description = "Tabular display with sort, filter, heatmap and CSV download"
    preview_id  = "table_view"

    metrics = [
        MetricControl(
            id="metric",
            label="Data element(s)",
            max_count=8,
            allowed_types=("aggregate", "indicator", "tracker_numeric"),
            default_agg="SUM",
        )
    ]
    dimensions = []
    options = [
        SelectControl("mode",      "Mode",       ("Aggregated", "Raw"),                           "Aggregated"),
        SelectControl("theme",     "Theme",       ("Default", "Blue", "Green", "Light", "Dark"),   "Default"),
        SelectControl("heatmap",   "Heatmap",     ("Off", "On"),                                   "Off"),
        SelectControl("stripe",    "Stripe rows", ("On", "Off"),                                   "On"),
        SelectControl("border",    "Border",      ("Light", "None", "Dark"),                       "Light"),
        SelectControl("font_size", "Font size",   ("Medium", "Small", "Large"),                    "Medium"),
    ]
    time_grain = TimeGrainControl(default="Monthly")

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        po = config.get("plugin_options") or {}
        return _helpers_js(n, po) + "\n" + _sample_js(n, po) + "\n" + _real_js(n, config, po)
