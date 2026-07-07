"""
TablePlugin — tabular display with sort, filter, heatmap, and CSV download.

Modes
-----
aggregated : analytics API -> org unit rows x period columns (pivoted)
raw        : analytics API -> flat rows, one column per response header

plugin_options keys
-------------------
mode         : Aggregated | Raw
theme        : Default | Blue | Green | Light | Dark
heatmap      : Off | On
stripe       : Off | On
border       : Light | None | Dark
font_size    : Medium | Small | Large
ou_hierarchy : Off | On   (raw tracker: add ancestor columns — province/district/…)
tracker_link : Off | On   (raw tracker: add a column linking each event to Tracker Capture)

Interactive (client-side, all modes)
------------------------------------
- click a row to highlight it
- per-column filters: dropdown for categorical (option-set / org unit) columns,
  a from/to pair for date columns, free text otherwise
"""
from __future__ import annotations

import json as _json

from charts.plugins.base import (
    ChartPlugin, DimensionControl, MetricControl, SelectControl, TimeGrainControl,
)

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

    # Preset OR a custom numeric font size (px) — REQ-UI-OPT-01.
    fs = (f"{str(font_size).strip()}px" if str(font_size).strip().isdigit()
          else {"Small": "11px", "Medium": "13px", "Large": "15px"}.get(font_size, "13px"))
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
    let _tS{n} = {{ sc:-1, sd:1, fi:{{}}, pg:0, ps:50, sel:-1 }};
    let _tD{n} = {{ cols:[], rows:[], ftypes:[], distinct:{{}}, linkCol:-1 }};

    function _tHeat{n}(v,mn,mx) {{
      if(mx<=mn) return '';
      const t=(v-mn)/(mx-mn);
      const r=Math.round(255+(_T{n}.accentR-255)*t);
      const g=Math.round(255+(_T{n}.accentG-255)*t);
      const b=Math.round(255+(_T{n}.accentB-255)*t);
      return `rgb(${{r}},${{g}},${{b}})`;
    }}

    function _tEsc{n}(v) {{ return String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}

    // Classify each column for its filter UI: 'link' | 'date' | 'select' | 'text'.
    // date  → from/to pickers; select → dropdown (option-set / org unit / few values).
    function _tClassify{n}(cols,rows,linkCol) {{
      const ftypes=[], distinct={{}};
      cols.forEach((c,ci)=>{{
        if(ci===linkCol){{ ftypes.push('link'); return; }}
        const vals=rows.map(r=>r[ci]).filter(v=>v!=null&&v!=='');
        if(!vals.length){{ ftypes.push('text'); return; }}
        const isDate=vals.every(v=>/^\\d{{4}}-\\d{{2}}-\\d{{2}}/.test(String(v)));
        if(isDate){{ ftypes.push('date'); return; }}
        const allNum=vals.every(v=>!isNaN(parseFloat(v))&&isFinite(v));
        const ds=Array.from(new Set(vals.map(String)));
        if(!allNum && ds.length<=50 && ds.length<vals.length){{
          ftypes.push('select');
          distinct[ci]=ds.sort((a,b)=>a.localeCompare(b));
        }} else {{ ftypes.push('text'); }}
      }});
      return {{ftypes,distinct}};
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
      const {{cols,rows,ftypes,distinct,linkCol}}=_tD{n};
      // Preserve focus/caret of the active text filter across the innerHTML rebuild.
      const _ae=document.activeElement;
      const _afi=(_ae&&_ae.dataset&&_ae.dataset.fi!=null)?_ae.dataset.fi:null;
      const _afd=(_ae&&_ae.dataset&&_ae.dataset.fd!=null)?_ae.dataset.fd:null;
      const _asel=(_ae&&_ae.selectionStart!=null)?_ae.selectionStart:null;

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
      // Apply per-column filters by type.
      Object.keys(st.fi).forEach(ci=>{{
        const fv=st.fi[ci]; const ft=ftypes[ci];
        if(ft==='date') {{
          const from=fv&&fv.from, to=fv&&fv.to;
          if(!from&&!to) return;
          disp=disp.filter(r=>{{ const d=String(r[ci]??'').substring(0,10); if(!d)return false;
            if(from&&d<from)return false; if(to&&d>to)return false; return true; }});
        }} else if(ft==='select') {{
          if(!fv) return;
          disp=disp.filter(r=>String(r[ci]??'')===fv);
        }} else {{
          if(!fv) return;
          const lo=String(fv).toLowerCase();
          disp=disp.filter(r=>String(r[ci]??'').toLowerCase().includes(lo));
        }}
      }});

      const bd=o.border;
      const thS=`background:${{o.hdrBg}};color:${{o.hdrFg}};padding:5px 8px;font-size:${{o.fs}};cursor:pointer;white-space:nowrap;${{bd}}position:sticky;top:0;z-index:1;user-select:none;`;
      const tdS=`padding:4px 8px;font-size:${{o.fs}};${{bd}}`;
      const fS=`padding:2px 4px;background:#f5f5f5;${{bd}}position:sticky;top:0;z-index:1;`;
      const inS=`width:100%;font-size:11px;border:1px solid #ccc;padding:2px 3px;box-sizing:border-box;background:white;`;

      let h=`<table style="width:100%;border-collapse:collapse;">`;
      h+='<thead><tr>'+cols.map((c,i)=>{{
        const arr=st.sc===i?(st.sd>0?' \\u25b2':' \\u25bc'):'';
        return `<th style="${{thS}}" data-sc="${{i}}">${{_tEsc{n}(c)}}${{arr}}</th>`;
      }}).join('')+'</tr>';
      h+='<tr>'+cols.map((_,i)=>{{
        const ft=ftypes[i];
        if(ft==='link') return `<td style="${{fS}}"></td>`;
        if(ft==='date') {{
          const f=st.fi[i]||{{}};
          return `<td style="${{fS}}"><div style="display:flex;gap:2px;">`
            +`<input type="date" data-fi="${{i}}" data-fd="from" value="${{f.from||''}}" title="From" style="${{inS}}">`
            +`<input type="date" data-fi="${{i}}" data-fd="to" value="${{f.to||''}}" title="To" style="${{inS}}">`
            +`</div></td>`;
        }}
        if(ft==='select') {{
          const cur=st.fi[i]||''; const ds=distinct[i]||[];
          return `<td style="${{fS}}"><select data-fi="${{i}}" style="${{inS}}">`
            +`<option value="">(All)</option>`
            +ds.map(v=>`<option value="${{_tEsc{n}(v)}}"${{v===cur?' selected':''}}>${{_tEsc{n}(v)}}</option>`).join('')
            +`</select></td>`;
        }}
        const fv=st.fi[i]||'';
        return `<td style="${{fS}}"><input type="text" placeholder="\\ud83d\\udd0d" value="${{_tEsc{n}(fv)}}" data-fi="${{i}}" style="${{inS}}"></td>`;
      }}).join('')+'</tr></thead><tbody>';

      // Pagination: slice the filtered+sorted rows to the current page.
      const total=disp.length;
      const ps=(st.ps!=null?st.ps:50);                       // 0 = show all
      const pageCount=ps>0?Math.max(1,Math.ceil(total/ps)):1;
      if(st.pg>=pageCount) st.pg=pageCount-1;
      if(st.pg<0) st.pg=0;
      const pageRows=ps>0?disp.slice(st.pg*ps,st.pg*ps+ps):disp;

      pageRows.forEach((row,ri)=>{{
        const rb=(ri%2===1)?o.stripe:'transparent';
        h+=`<tr data-bg="${{rb}}" style="background:${{rb}};cursor:pointer;">`;
        row.forEach((cell,ci)=>{{
          if(ci===linkCol){{
            const url=cell||'';
            const a=url?`<a href="${{_tEsc{n}(url)}}" target="_blank" rel="noopener noreferrer" class="tcap{n}" style="color:#1a6fa8;font-weight:600;text-decoration:none;">Open \\u2197</a>`:'';
            h+=`<td style="${{tdS}}">${{a}}</td>`;
            return;
          }}
          let bg='';
          if(o.heatmap&&cm[ci]!==undefined){{
            const v=parseFloat(cell);
            if(!isNaN(v))bg=`background:${{_tHeat{n}(v,cm[ci],cx[ci])}};`;
          }}
          h+=`<td style="${{tdS}}${{bg}}">${{_tEsc{n}(cell)}}</td>`;
        }});
        h+='</tr>';
      }});
      h+='</tbody></table>';

      wrap.querySelector('[data-tb="{n}"]').innerHTML=h;

      // Freeze the filter row directly under the (sticky) header.
      const _thead=wrap.querySelector('[data-tb="{n}"] thead');
      if(_thead){{
        const _hr=_thead.querySelector('tr:first-child');
        const _hh=_hr?_hr.offsetHeight:0;
        _thead.querySelectorAll('tr:nth-child(2) td').forEach(td=>{{td.style.top=_hh+'px';}});
      }}

      // Footer: row range + page indicator + prev/next enabled state.
      const _ft=wrap.querySelector('[data-tf="{n}"]');
      if(_ft){{
        if(total===0) _ft.textContent='0 rows';
        else if(ps<=0) _ft.textContent=`${{total}} row${{total===1?'':'s'}}`;
        else {{ const a=st.pg*ps+1, b=Math.min(total,(st.pg+1)*ps);
                _ft.textContent=`${{a}}\\u2013${{b}} of ${{total}}`; }}
      }}
      const _pi=wrap.querySelector('[data-tpi="{n}"]');
      if(_pi) _pi.textContent=`Page ${{st.pg+1}}/${{pageCount}}`;
      const _pp=wrap.querySelector('[data-tp="prev"]'); if(_pp) _pp.disabled=(st.pg<=0);
      const _pn=wrap.querySelector('[data-tp="next"]'); if(_pn) _pn.disabled=(st.pg>=pageCount-1);

      // Sort on header click.
      wrap.querySelectorAll('th[data-sc]').forEach(th=>
        th.addEventListener('click',()=>{{
          const c=+th.dataset.sc;
          _tS{n}.sd=(_tS{n}.sc===c?-_tS{n}.sd:1);
          _tS{n}.sc=c; _tS{n}.pg=0; _tRender{n}(wrap);
        }})
      );
      // Text filters (live), select + date filters (on change).
      wrap.querySelectorAll('input[data-fi]:not([data-fd])').forEach(inp=>
        inp.addEventListener('input',()=>{{ _tS{n}.fi[inp.dataset.fi]=inp.value; _tS{n}.pg=0; _tRender{n}(wrap); }}));
      wrap.querySelectorAll('select[data-fi]').forEach(sel=>
        sel.addEventListener('change',()=>{{ _tS{n}.fi[sel.dataset.fi]=sel.value; _tS{n}.pg=0; _tRender{n}(wrap); }}));
      wrap.querySelectorAll('input[data-fd]').forEach(inp=>
        inp.addEventListener('change',()=>{{
          const ci=inp.dataset.fi; const cur=_tS{n}.fi[ci]||{{}};
          cur[inp.dataset.fd]=inp.value; _tS{n}.fi[ci]=cur; _tS{n}.pg=0; _tRender{n}(wrap);
        }}));
      // Row click → highlight the clicked row (clears any previous highlight).
      wrap.querySelectorAll('tbody tr').forEach(tr=>
        tr.addEventListener('click',ev=>{{
          if(ev.target.closest('a')) return;   // let link clicks through
          wrap.querySelectorAll('tbody tr').forEach(x=>{{ x.style.background=x.dataset.bg||'transparent'; }});
          tr.style.background='#fde68a';
        }}));
      // Tracker Capture links open a NEW tab via the top window (srcdoc iframe is sandboxed).
      wrap.querySelectorAll('a.tcap{n}').forEach(a=>
        a.addEventListener('click',ev=>{{
          ev.preventDefault(); ev.stopPropagation();
          const u=a.getAttribute('href');
          try {{ (window.top||window).open(u,'_blank','noopener'); }} catch(_e) {{ window.open(u,'_blank','noopener'); }}
        }}));

      // Restore filter focus/caret.
      if(_afi!=null){{
        const sel='[data-fi="'+_afi+'"]'+(_afd?'[data-fd="'+_afd+'"]':':not([data-fd])');
        const el=wrap.querySelector(sel);
        if(el){{ el.focus(); if(_asel!=null&&el.setSelectionRange){{ try{{el.setSelectionRange(_asel,_asel);}}catch(e){{}} }} }}
      }}
    }}

    function _tMount{n}(cvs,cols,rows,meta) {{
      meta=meta||{{}};
      const linkCol=(meta.linkCol!=null?meta.linkCol:-1);
      cvs.style.display='none';
      const par=cvs.parentElement;
      let wrap=par.querySelector('[data-tw="{n}"]');
      if(!wrap){{
        wrap=document.createElement('div');
        wrap.setAttribute('data-tw','{n}');
        wrap.style.cssText='position:absolute;top:0;left:0;width:100%;height:100%;display:flex;flex-direction:column;background:white;';
        const body=document.createElement('div');
        body.setAttribute('data-tb','{n}');
        body.style.cssText='flex:1;overflow:auto;';
        const foot=document.createElement('div');
        foot.style.cssText='display:flex;align-items:center;justify-content:space-between;gap:8px;'
          +'padding:4px 8px;background:#f8f9fa;border-top:1px solid #dee2e6;flex-shrink:0;';
        const _btn='font-size:11px;padding:2px 8px;cursor:pointer;border:1px solid #aaa;background:white;border-radius:3px;';
        foot.innerHTML=
          '<button onclick="_tCSV{n}()" style="'+_btn+'">&#8595; Download CSV</button>'
          +'<span style="display:flex;align-items:center;gap:6px;font-size:11px;color:#566573;">'
          +  '<button data-tp="prev" style="'+_btn+'">&#8249; Prev</button>'
          +  '<span data-tpi="{n}"></span>'
          +  '<button data-tp="next" style="'+_btn+'">Next &#8250;</button>'
          +  '<select data-tps="{n}" style="font-size:11px;padding:1px 2px;">'
          +    '<option value="25">25/page</option><option value="50" selected>50/page</option>'
          +    '<option value="100">100/page</option><option value="200">200/page</option>'
          +    '<option value="0">All</option></select>'
          +  '<span data-tf="{n}"></span>'
          +'</span>';
        wrap.appendChild(body);
        wrap.appendChild(foot);
        par.appendChild(wrap);
        foot.querySelector('[data-tp="prev"]').addEventListener('click',()=>{{
          if(_tS{n}.pg>0){{_tS{n}.pg--;_tRender{n}(wrap);}} }});
        foot.querySelector('[data-tp="next"]').addEventListener('click',()=>{{
          _tS{n}.pg++;_tRender{n}(wrap); }});
        foot.querySelector('[data-tps="{n}"]').addEventListener('change',e=>{{
          _tS{n}.ps=+e.target.value;_tS{n}.pg=0;_tRender{n}(wrap); }});
      }}
      const cl=_tClassify{n}(cols,rows,linkCol);
      _tD{n}={{cols,rows,ftypes:cl.ftypes,distinct:cl.distinct,linkCol}};
      const _psSel=wrap.querySelector('[data-tps="{n}"]');
      const _ps=_psSel?+_psSel.value:50;
      _tS{n}={{sc:-1,sd:1,fi:{{}},pg:0,ps:_ps,sel:-1}};
      _tRender{n}(wrap);
    }}
"""


def _sample_js(n: int, po: dict, config: dict | None = None) -> str:
    mode = _po(po, "mode", "Aggregated")
    if mode == "Raw":
        cols, rows = _SAMPLE_RAW_COLS, _SAMPLE_RAW_ROWS
    else:
        # Aggregated preview reflects the real layout: columns = selected metrics,
        # rows = a single total unless disaggregated by org unit and/or period.
        metrics = (config or {}).get("metrics") or []
        names = [m.get("name") or m.get("uid") or f"Metric {i+1}"
                 for i, m in enumerate(metrics)] or ["Cases"]
        # Rows are disaggregated by the selected dimensions (DE/PA); columns = metrics.
        dim_names = [d.get("name") or d.get("uid")
                     for d in ((config or {}).get("dimensions") or {}).get("group_by", [])
                     if d.get("uid")]
        cols = dim_names + names

        def _vals(seed):
            return [str((seed * 37 + j * 53) % 380 + 20) for j in range(len(names))]

        rows = []
        if dim_names:
            for i in range(3):                          # 3 representative dimension combos
                rows.append([f"{dn} {i + 1}" for dn in dim_names] + _vals(i))
        else:
            rows.append(_vals(3))                       # single total row
    cols_js = _json.dumps(cols)
    rows_js = _json.dumps(rows)
    return f"""\
    function renderChart{n}Sample(cvs) {{
      _tMount{n}(cvs, {cols_js}, {rows_js});
    }}"""


def _real_js(n: int, config: dict, po: dict) -> str:
    import json as _j
    mode     = _po(po, "mode", "Aggregated")
    ou_hier  = _po(po, "ou_hierarchy", "Off") == "On"
    trk_link = _po(po, "tracker_link", "Off") == "On"
    metrics  = config.get("metrics", [])
    extra    = ChartPlugin._extra_params(config)
    source   = config.get("source") or {}
    src_type = source.get("type", "") or (metrics[0].get("type", "") if metrics else "")
    is_tracker = src_type in ("tracker_option", "tracker_numeric")
    prog_uid = source.get("prog_uid", "") or (metrics[0].get("prog_uid", "") if metrics else "")
    stage_uid = source.get("stage_uid", "") or (metrics[0].get("stage_uid", "") if metrics else "")

    # Build options lookup: { deUid: { code: displayName, ... } }
    opts_map = {}
    for m in metrics:
        if m.get("options"):
            opts_map[m["uid"]] = {o["code"]: o["name"] for o in m["options"]}
    opts_js = _j.dumps(opts_map)

    dx_uids = ";".join(m["uid"] for m in metrics if m.get("uid"))

    if mode == "Raw" and is_tracker and prog_uid:
        de_dims = "&".join(
            f"dimension={stage_uid}.{m['uid']}"
            for m in metrics if m.get("uid")
        )
        metrics_js = _j.dumps([
            {"uid": m["uid"], "name": m.get("name", m["uid"]),
             "stage": m.get("stage_uid") or stage_uid}
            for m in metrics if m.get("uid")
        ])
        ou_hier_js = "true" if ou_hier else "false"
        trk_link_js = "true" if trk_link else "false"
        prog_js = _j.dumps(prog_uid)
        fetch_block = f"""\
            const OPTS_MAP{n} = {opts_js};
            const METRICS{n}  = {metrics_js};
            const OU_HIER{n}  = {ou_hier_js};
            const TRK_LINK{n} = {trk_link_js};
            const PROG{n}     = {prog_js};
            // Capture root from document.baseURI (srcdoc-safe; matches dhis2Get's '../').
            let TCAP_ROOT{n}=''; try {{ TCAP_ROOT{n}=new URL('../',document.baseURI).href; }} catch(_e) {{}}
            const rpe=resolveRelativePeriod(pe);
            // Org-unit ancestor names (province/district/…) when the hierarchy option is on.
            let LEVELNAMES{n}={{}};
            if(OU_HIER{n}) {{
              try {{ const lv=await dhis2Get('api/organisationUnitLevels.json?fields=level,name&paging=false');
                (lv.organisationUnitLevels||[]).forEach(l=>{{LEVELNAMES{n}[l.level]=l.name;}}); }} catch(_e) {{}}
            }}
            const d=await dhis2Get(
              'api/analytics/events/query/{prog_uid}'
              +'?stage={stage_uid}'
              +'&dimension=pe:'+encodeURIComponent(rpe)
              +'&dimension=ou:'+encodeURIComponent(ou)
              +'&{de_dims}'
              +'&displayProperty=NAME&paging=false'
              +(OU_HIER{n}?'&hierarchyMeta=true':'')+'{extra}'
            );
            const hdrs=d.headers||[];
            const meta=d.metaData||{{}}; const items=meta.items||{{}}; const ouH=meta.ouHierarchy||{{}};
            const dateI=hdrs.findIndex(h=>h.name==='eventdate');
            const ouNmI=hdrs.findIndex(h=>h.name==='ouname');
            const ouI  =hdrs.findIndex(h=>h.name==='ou');
            const teiI =hdrs.findIndex(h=>h.name==='tei');
            const mIdx=METRICS{n}.map(m=>{{
              let i=hdrs.findIndex(h=>h.name===m.stage+'.'+m.uid);
              if(i<0) i=hdrs.findIndex(h=>h.name===m.uid);
              return i;
            }});
            // Ancestor levels to show (2..deepest), skipping national level 1.
            let ancLevels=[];
            if(OU_HIER{n}) {{
              let maxd=0;
              (d.rows||[]).forEach(r=>{{ const a=(ouH[r[ouI]]||'').split('/').filter(Boolean); if(a.length>maxd)maxd=a.length; }});
              for(let L=2; L<=maxd; L++) ancLevels.push(L);
            }}
            const hierCols=ancLevels.map(L=>LEVELNAMES{n}[L]||('Level '+L));
            const cols=['Event date',...hierCols,'Org unit',...METRICS{n}.map(m=>m.name)];
            let linkCol=-1;
            if(TRK_LINK{n}) {{ cols.push('Open'); linkCol=cols.length-1; }}
            const rows=(d.rows||[]).map(r=>{{
              const dateTxt=dateI>=0?(r[dateI]||'').substring(0,10):'';
              const ouUid=ouI>=0?r[ouI]:'';
              const ouTxt=ouNmI>=0?(r[ouNmI]||''):(items[ouUid]?.name||'');
              const anc=(ouH[ouUid]||'').split('/').filter(Boolean);
              const hierCells=ancLevels.map(L=>{{ const uid=anc[L-1]; return uid?(items[uid]?.name||''):''; }});
              const metricCells=METRICS{n}.map((m,k)=>{{
                const idx=mIdx[k]; const val=idx>=0?r[idx]:'';
                const om=OPTS_MAP{n}[m.uid];
                return om&&om[val]!=null ? om[val] : (val??'');
              }});
              const out=[dateTxt,...hierCells,ouTxt,...metricCells];
              if(TRK_LINK{n}) {{
                const tei=teiI>=0?r[teiI]:'';
                out.push((TCAP_ROOT{n}&&tei)
                  ? (TCAP_ROOT{n}+'dhis-web-tracker-capture/index.html#/dashboard?tei='+tei+'&program='+PROG{n}+'&ou='+ouUid)
                  : '');
              }}
              return out;
            }});
            _tMount{n}(cvs,cols,rows,{{linkCol:linkCol}});"""
    elif mode == "Raw":
        fetch_block = f"""\
            const d=await dhis2Get(
              'api/analytics.json?dimension=dx:{dx_uids}'
              +'&dimension=pe:'+encodeURIComponent(resolveRelativePeriod(pe))
              +'&dimension=ou:'+encodeURIComponent(ou)
              +'&displayProperty=NAME&paging=false{extra}'
            );
            const meta=d.metaData?.items||{{}};
            const cols=d.headers.map(h=>h.column);
            const rows=(d.rows||[]).map(r=>r.map(v=>meta[v]?.name||v));
            _tMount{n}(cvs,cols,rows);"""
    else:
        # Aggregated: columns are the SELECTED METRICS. Org unit & period are FILTERS
        # (one total row) unless the user adds DIMENSIONS (DE/PA) to split rows by.
        dims = [d for d in ((config.get("dimensions") or {}).get("group_by") or []) if d.get("uid")]
        dims_js = _j.dumps([
            {"uid": d["uid"], "name": d.get("name", d["uid"]),
             "stage": d.get("stage_uid") or stage_uid, "is_tea": bool(d.get("is_tea")),
             "options": d.get("options", [])}
            for d in dims
        ])
        metrics_js = _j.dumps([
            {"uid": m["uid"], "name": m.get("name", m["uid"]), "type": m.get("type", ""),
             "agg": m.get("agg", "SUM"), "stage": m.get("stage_uid") or stage_uid}
            for m in metrics if m.get("uid")
        ])
        if is_tracker and prog_uid:
            de_dims = "&".join(f"dimension={stage_uid}.{m['uid']}"
                               for m in metrics if m.get("uid"))
            # Dimension DEs/PAs are appended by {extra} (group_by) so events/query returns
            # them as columns; we group per-event rows by them and aggregate the metrics.
            fetch_block = f"""\
            const METRICS{n} = {metrics_js};
            const DIMS{n}    = {dims_js};
            const rpe=resolveRelativePeriod(pe);
            const d=await dhis2Get(
              'api/analytics/events/query/{prog_uid}?stage={stage_uid}'
              +'&dimension=pe:'+encodeURIComponent(rpe)
              +'&dimension=ou:'+encodeURIComponent(ou)
              +'&{de_dims}'
              +'&displayProperty=NAME&paging=false{extra}'
            );
            const H=d.headers||[];
            const ci=name=>H.findIndex(h=>h.name===name);
            const dimI=DIMS{n}.map(dm=>{{ let i=ci((dm.is_tea?dm.uid:dm.stage+'.'+dm.uid)); if(i<0)i=ci(dm.uid); return i; }});
            const metI=METRICS{n}.map(m=>{{ let i=ci(m.stage+'.'+m.uid); if(i<0)i=ci(m.uid); return i; }});
            const dimNameMaps=DIMS{n}.map(dm=>{{ const mp={{}}; (dm.options||[]).forEach(o=>mp[o.code]=o.name); return mp; }});
            const groups={{}};
            (d.rows||[]).forEach(r=>{{
              const keyVals=DIMS{n}.map((dm,di)=>(dimI[di]>=0?(r[dimI[di]]||''):''));
              const key=keyVals.join('\\u0001');
              if(!groups[key]) groups[key]={{vals:keyVals, acc:METRICS{n}.map(()=>({{sum:0,cnt:0,min:Infinity,max:-Infinity}}))}};
              METRICS{n}.forEach((m,mi)=>{{
                const raw=metI[mi]>=0?r[metI[mi]]:'';
                if(raw==='' || raw==null) return;
                const a=groups[key].acc[mi]; a.cnt++;
                const num=parseFloat(raw);
                if(!isNaN(num)){{ a.sum+=num; if(num<a.min)a.min=num; if(num>a.max)a.max=num; }}
              }});
            }});
            function _agg(a,agg){{
              switch(agg){{
                case 'COUNT': return a.cnt;
                case 'AVERAGE': return a.cnt?+(a.sum/a.cnt).toFixed(2):0;
                case 'MIN': return (a.cnt&&a.min!==Infinity)?a.min:0;
                case 'MAX': return (a.cnt&&a.max!==-Infinity)?a.max:0;
                default: return a.sum;
              }}
            }}
            const cols=[...DIMS{n}.map(dm=>dm.name), ...METRICS{n}.map(m=>m.name)];
            const keys=Object.keys(groups).sort();
            const rows=keys.map(k=>{{
              const g=groups[k];
              const labels=g.vals.map((code,di)=>dimNameMaps[di][code]||code||'(blank)');
              const vals=METRICS{n}.map((m,mi)=>{{
                const isCount=(m.type==='tracker_option')||((m.agg||'SUM')==='COUNT');
                return isCount ? g.acc[mi].cnt : _agg(g.acc[mi], m.agg||'SUM');
              }});
              return [...labels, ...vals];
            }});
            _tMount{n}(cvs,cols,rows);"""
        else:
            # Non-tracker (aggregate / indicator): one total row, metrics as columns,
            # org unit + period as filters (no DE/PA disaggregation applies).
            filt = ChartPlugin._filter_params(config)
            filt = ("&" + filt) if filt else ""
            fetch_block = f"""\
            const METRICS{n} = {metrics_js};
            const d=await dhis2Get(
              'api/analytics.json?dimension=dx:{dx_uids}'
              +'&filter=ou:'+encodeURIComponent(ou)
              +'&filter=pe:'+encodeURIComponent(pe)
              +'&displayProperty=NAME{filt}'
            );
            const H=d.headers||[];
            const dxI=H.findIndex(h=>h.name==='dx');
            const vI =H.findIndex(h=>h.name==='value');
            const byDx={{}};
            (d.rows||[]).forEach(r=>{{ if(dxI>=0&&vI>=0) byDx[r[dxI]]=r[vI]; }});
            const cols=METRICS{n}.map(m=>m.name);
            const rows=[METRICS{n}.map(m=>byDx[m.uid]!=null?byDx[m.uid]:'')];
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
            allowed_types=("aggregate", "indicator", "tracker_numeric", "tracker_option"),
            default_agg="SUM",
        )
    ]
    dimensions = [
        DimensionControl(
            id="dimension",
            label="Disaggregate by (rows)",
            allowed_types=("tracker_option", "tracker_numeric"),
            required=False,
            max_count=4,
            show_alias=True,
            hint="Pick DE/PA(s) to split rows by (e.g. Sex, Species); alias = column header",
        )
    ]
    options = [
        SelectControl("mode",         "Mode",            ("Aggregated", "Raw"),                         "Aggregated"),
        SelectControl("ou_hierarchy", "OU hierarchy",    ("Off", "On"),                                 "Off"),
        SelectControl("tracker_link", "Tracker link",    ("Off", "On"),                                 "Off"),
        SelectControl("theme",        "Theme",           ("Default", "Blue", "Green", "Light", "Dark"), "Default"),
        SelectControl("heatmap",      "Heatmap",         ("Off", "On"),                                 "Off"),
        SelectControl("stripe",       "Stripe rows",     ("On", "Off"),                                 "On"),
        SelectControl("border",       "Border",          ("Light", "None", "Dark"),                     "Light"),
        SelectControl("font_size",    "Font size",       ("Medium", "Small", "Large"),                  "Medium"),
    ]
    time_grain = TimeGrainControl(default="Monthly")

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        po = config.get("plugin_options") or {}
        return _helpers_js(n, po) + "\n" + _sample_js(n, po, config) + "\n" + _real_js(n, config, po)
