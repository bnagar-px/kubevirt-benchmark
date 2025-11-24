#!/usr/bin/env python3
"""
Generate an interactive HTML dashboard for KubeVirt performance test results.

Structure:
  PX Version (top-level tab)
    └── Disk Count tab (e.g., 1-disk, 2-disk, 4-disk)
          ├── 3 compact charts (Creation / Boot Storm / Migration) with times in mm:ss
          └── VM Size tabs (e.g., 50 VMs, 100 VMs, 200 VMs, 400 VMs)
                ├── Creation + Boot Storm subtab (original tables intact)
                └── Live Migration subtab (original tables intact)

Usage:
  python3 generate_dashboard.py [--days N] [--base-dir PATH] [--output-html FILE]
"""

import json
import argparse
import pandas as pd
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict


LABEL_MAP = {
    "running_time_sec": "Running Time",
    "ping_time_sec": "Ping Time",
    "clone_duration_sec": "Clone Duration",
    "observed_time_sec": "Observed Time",
    "vmim_time_sec": "VMIM Time",
}

# ---------------- Utility Functions ----------------
def load_json(path: Path):
    """Safely load JSON file; return None if not found or invalid."""
    try:
        if not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None

def load_cluster_info(yaml_path: str):
    """Load cluster info YAML for a single cluster."""
    path = Path(yaml_path)
    if not path.exists():
        print(f"Cluster info file not found: {yaml_path}")
        return None

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return data.get("cluster", {})
    except Exception as e:
        print(f"⚠️  Failed to parse {yaml_path}: {e}")
        return None

def build_cluster_info_tab(cluster_info: dict) -> str:
    """Render the cluster info as an HTML table with auto-generated labels from keys."""
    if not cluster_info:
        return "<p>No cluster information provided.</p>"

    rows = ""
    for key, value in cluster_info.items():
        label = key.replace("_", " ").upper()

        if isinstance(value, str) and "\n" in value:
            rows += f"<tr><th>{label}</th><td><pre style='margin:0;white-space:pre-wrap'>{value.strip()}</pre></td></tr>"
        else:
            rows += f"<tr><th>{label}</th><td>{value}</td></tr>"

    return f"<table class='table table-bordered w-auto'><tbody>{rows}</tbody></table>"

def load_manual_results(yaml_path: str):
    """Load manual results YAML."""
    path = Path(yaml_path)
    if not path.exists():
        print(f"Manual results file not found: {yaml_path}")
        return None
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return data.get("results", [])
    except Exception as e:
        print(f"⚠️  Failed to parse {yaml_path}: {e}")
        return None


def build_manual_results_tab(manual_results: list) -> str:
    """Render manual results as an interactive table."""
    if not manual_results:
        return "<p>No manual results provided.</p>"

    df = pd.DataFrame(manual_results)
    if df.empty:
        return "<p>Manual results file is empty.</p>"

    # Round any numeric columns and apply friendly names
    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].round(2)

    return df.to_html(
        classes="display compact nowrap",
        table_id="table_manual_results",
        index=False,
        border=0
    )

def format_folder_name(folder_name: str) -> str:
    """Convert '20251014-165952_kubevirt-perf-test_1-50' → '2025-10-14 16:59:52 — 50 VMs'"""
    try:
        parts = folder_name.split("_")
        timestamp = parts[0]
        vm_range = parts[-1]
        dt = datetime.strptime(timestamp, "%Y%m%d-%H%M%S")

        if "-" in vm_range:
            start_str, end_str = vm_range.split("-")
            start = int(start_str)
            end = int(end_str)
            num_vms = (end - start) + 1
        else:
            num_vms = int(vm_range)

        suffix = "VM" if num_vms == 1 else "VMs"
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} — {num_vms} {suffix}"
    except Exception:
        return folder_name


def summary_to_df(summary_json):
    """
    Convert a summary JSON into a DataFrame for display.
    Ensures friendly metric names and rounds all numeric columns to 2 decimals.
    """
    if not summary_json or "metrics" not in summary_json:
        return pd.DataFrame(), None, None

    rows = []
    difference_row = None

    for m in summary_json["metrics"]:
        metric = m.get("metric")
        if metric == "difference_observed_vmim_sec":
            difference_row = m
            continue

        # Apply friendly names and rounding
        rows.append({
            "Metric": LABEL_MAP.get(metric, metric),
            "Average (s)": round(m.get("avg", 0), 2) if m.get("avg") is not None else None,
            "Max (s)": round(m.get("max", 0), 2) if m.get("max") is not None else None,
            "Min (s)": round(m.get("min", 0), 2) if m.get("min") is not None else None,
            "Count": m.get("count", ""),
        })

    df = pd.DataFrame(rows)
    total_info = {
        "total_vms": summary_json.get("total_vms"),
        "successful": summary_json.get("successful"),
        "failed": summary_json.get("failed")
    }
    return df, difference_row, total_info


def df_to_html_table(df: pd.DataFrame, table_id: str) -> str:
    """
    Convert DataFrame into an interactive HTML table (DataTables style).
    Applies consistent label mapping and rounds numeric values to 2 decimals
    for both summary and detailed result tables.
    """
    if df is None or df.empty:
        return f"<p>No data found for {table_id}</p>"

    column_rename_map = {
        "namespace": "Namespace",
        "running_time_sec": "Running Time (s)",
        "ping_time_sec": "Ping Time (s)",
        "clone_duration_sec": "Clone Duration (s)",
        "observed_time_sec": "Observed Time (s)",
        "vmim_time_sec": "VMIM Time (s)",
        "success": "Success",
        "status": "Status",
        "source_node": "Source Node",
        "target_node": "Target Node",
    }

    # Rename columns if present
    df = df.rename(columns={k: v for k, v in column_rename_map.items() if k in df.columns})

    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].round(2)

    if "Success" in df.columns:
        df["Success"] = df["Success"].map({True: "✅ True", False: "❌ False"})

    return df.to_html(
        classes="display compact nowrap",
        table_id=table_id,
        index=False,
        border=0
    )

def get_vm_count_from_folder(folder_name: str) -> int:
    """Extract VM count from folder suffix."""
    try:
        vm_range = folder_name.split("_")[-1]
        if "-" in vm_range:
            start_str, end_str = vm_range.split("-")
            start = int(start_str)
            end = int(end_str)
            return (end - start) + 1
        return int(vm_range)
    except Exception:
        return 0


def format_mmss(seconds: float) -> str:
    """Format seconds → mm:ss"""
    if seconds is None:
        return "0:00"
    total = int(round(seconds))
    m = total // 60
    s = total % 60
    return f"{m}:{s:02d}"


# ---------------- Chart Builder ----------------
def build_bar_chart_mmss(records, title, color, chart_id):
    """Builds a compact 30%-width bar chart with mm:ss formatting and folder name in hover."""
    if not records:
        return f"<div class='col-12 col-md-4'><p>No data for {title}</p></div>"

    df = pd.DataFrame(records).sort_values("VMs")
    x_vals = df["VMs"].tolist()
    y_secs = df["Seconds"].tolist()
    folder_labels = df["Folder"].tolist()  # used in hover only

    max_sec = max(y_secs) if y_secs else 0
    step = 10 if max_sec <= 60 else 30 if max_sec <= 180 else 60 if max_sec <= 600 else 120
    ticks = list(range(0, int(max_sec + step), step))
    ticktext = [format_mmss(t) for t in ticks]

    return f"""
    <div class="col-12 col-md-4">
      <div id="{chart_id}" class="plotly-chart" style="height:360px; width:100%;"></div>
      <script>
        Plotly.newPlot('{chart_id}', [{{
          x: {x_vals},
          y: {y_secs},
          type: 'bar',
          marker: {{
            color: '{color}',
            line: {{color: 'rgba(0,0,0,0.35)', width: 1}}
          }},
          hovertemplate: 'Folder: %{{text}}<br>VMs: %{{x}}<br>Duration: %{{customdata}}<extra></extra>',
          text: {folder_labels},
          customdata: { [format_mmss(v) for v in y_secs] },
          textposition: 'none'
        }}], {{
          title: '{title}',
          xaxis: {{
            title: 'Total VMs',
            type: 'category',
            categoryorder: 'array',
            categoryarray: {x_vals}
          }},
          yaxis: {{
            title: 'Duration (mm:ss)',
            tickmode: 'array',
            tickvals: {ticks},
            ticktext: {ticktext}
          }},
          margin: {{t: 50, l: 50, r: 20, b: 50}},
          bargap: 0.3
        }}, {{responsive: true,  displayModeBar: false}});
      </script>
    </div>
    """


# ---------------- Folder Builders ----------------
def build_creation_boot_content(folder: Path, uid: str) -> str:
    """Creation + Boot Storm section (original style)."""
    creation_summary = load_json(folder / "summary_vm_creation_results.json")
    boot_summary = load_json(folder / "summary_boot_storm_results.json")
    creation_results = load_json(folder / "vm_creation_results.json")
    boot_results = load_json(folder / "boot_storm_results.json")

    creation_df = pd.DataFrame(creation_results or [])
    boot_df = pd.DataFrame(boot_results or [])
    if not creation_df.empty and "success" in creation_df.columns:
        cols = [c for c in creation_df.columns if c != "success"] + ["success"]
        creation_df = creation_df[cols]

    creation_summary_df, _, creation_total_info = summary_to_df(creation_summary)
    boot_summary_df, _, boot_total_info = summary_to_df(boot_summary)
    creation_total_info = creation_total_info or {}
    boot_total_info = boot_total_info or {}

    creation_total_time = creation_summary.get("total_test_duration_sec") if creation_summary else None
    boot_total_time = boot_summary.get("total_test_duration_sec") if boot_summary else None

    header_html = (
        f'<h6><strong>Results Directory:</strong> {folder.name}</h6>'
        f'<h6><strong>Total VMs:</strong> {creation_total_info.get("total_vms", "?")}</h6>'
        f'{f"<h6><strong>Total Creation Duration:</strong> {creation_total_time:.2f} s</h6>" if creation_total_time else ""}'
        f'{f"<h6><strong>Total Boot Storm Duration:</strong> {boot_total_time:.2f} s</h6>" if boot_total_time else ""}'
    )

    creation_summary_html = df_to_html_table(creation_summary_df, f"table_summary_creation_{uid}")
    boot_summary_html = df_to_html_table(boot_summary_df, f"table_summary_boot_{uid}")
    creation_html = df_to_html_table(creation_df, f"table_creation_{uid}")
    boot_html = df_to_html_table(boot_df, f"table_boot_{uid}")

    return f"""
    <div class="mb-4">
      {header_html}

      <h4 class="mt-4">Creation Summary</h4>
      {creation_summary_html}
      <p><strong>Total VMs:</strong> {creation_total_info.get("total_vms", "N/A")} |
         <strong>Successful:</strong> {creation_total_info.get("successful", "N/A")} |
         <strong>Failed:</strong> {creation_total_info.get("failed", "N/A")}</p>

      <h4 class="mt-5">Boot Storm Summary</h4>
      {boot_summary_html}
      <p><strong>Total VMs:</strong> {boot_total_info.get("total_vms", "N/A")} |
         <strong>Successful:</strong> {boot_total_info.get("successful", "N/A")} |
         <strong>Failed:</strong> {boot_total_info.get("failed", "N/A")}</p>

      <h4 class="mt-5">Creation Results</h4>
      {creation_html}

      <h4 class="mt-5">Boot Storm Results</h4>
      {boot_html}
    </div>
    """


def build_migration_content(folder: Path, uid: str) -> str:
    """Live Migration section (original style)."""
    migration_summary = load_json(folder / "summary_migration_results.json")
    migration_results = load_json(folder / "migration_results.json")

    migration_df = pd.DataFrame(migration_results or [])
    if not migration_df.empty and "status" in migration_df.columns:
        cols = [c for c in migration_df.columns if c != "status"] + ["status"]
        migration_df = migration_df[cols]

    migration_summary_df, migration_diff_row, migration_total_info = summary_to_df(migration_summary)
    migration_total_info = migration_total_info or {}
    total_time = migration_summary.get("total_migration_duration_sec") or migration_summary.get("total_test_duration_sec") if migration_summary else None

    header_html = (
        f'<h6><strong>Results Directory:</strong> {folder.name}</h6>'
        f'<h6><strong>Total VMs:</strong> {migration_total_info.get("total_vms", "?")}</h6>'
        f'{f"<h6><strong>Total Migration Duration:</strong> {total_time:.2f} s</h6>" if total_time else ""}'
    )

    migration_summary_html = df_to_html_table(migration_summary_df, f"table_summary_migration_{uid}")
    migration_html = df_to_html_table(migration_df, f"table_migration_{uid}")

    diff_line = (
        f"<p><strong>Average Difference (Observed - VMIM):</strong> "
        f"{migration_diff_row.get('avg', 'N/A')} s</p>" if migration_diff_row else ""
    )

    return f"""
    <div class="mb-4">
      {header_html}

      <h4 class="mt-4">Migration Summary</h4>
      {migration_summary_html}
      <p><strong>Total VMs:</strong> {migration_total_info.get("total_vms", "N/A")} |
         <strong>Successful:</strong> {migration_total_info.get("successful", "N/A")} |
         <strong>Failed:</strong> {migration_total_info.get("failed", "N/A")}</p>
      {diff_line}

      <h4 class="mt-5">Migration Results (Per VM)</h4>
      {migration_html}
    </div>
    """


# ---------------- Disk and PX Builders ----------------
def build_disk_tab(px_version: str, disk_name: str, folders: list) -> str:
    """Disk-level tab with charts and nested VM-size tabs."""
    creation_rec, boot_rec, mig_rec = [], [], []
    by_vms = defaultdict(list)

    for folder in sorted(folders, key=lambda p: p.name):
        vms = get_vm_count_from_folder(folder.name)
        by_vms[vms].append(folder)
        csum = load_json(folder / "summary_vm_creation_results.json")
        bsum = load_json(folder / "summary_boot_storm_results.json")
        msum = load_json(folder / "summary_migration_results.json")
        if csum and csum.get("total_test_duration_sec"):
            creation_rec.append({"VMs": csum.get("total_vms", vms), "Seconds": csum["total_test_duration_sec"], "Folder": folder.name})
        if bsum and bsum.get("total_test_duration_sec"):
            boot_rec.append({"VMs": bsum.get("total_vms", vms), "Seconds": bsum["total_test_duration_sec"], "Folder": folder.name})
        if msum and (msum.get("total_migration_duration_sec") or msum.get("total_test_duration_sec")):
            total = msum.get("total_migration_duration_sec") or msum.get("total_test_duration_sec")
            mig_rec.append({"VMs": msum.get("total_vms", vms), "Seconds": total, "Folder": folder.name})

    charts_html = f"""
    <div class="container-fluid mt-3">
      <div class="row g-3">
        {build_bar_chart_mmss(creation_rec, "Creation Duration", "rgb(26,118,255)", f"chart_{px_version}_{disk_name}_creation")}
        {build_bar_chart_mmss(boot_rec, "Boot Storm Duration", "rgb(0,204,150)", f"chart_{px_version}_{disk_name}_boot")}
        {build_bar_chart_mmss(mig_rec, "Live Migration Duration", "rgb(255,99,71)", f"chart_{px_version}_{disk_name}_mig")}
      </div>
      <hr>
    </div>
    """

    # VM-size nested tabs
    vm_sizes_sorted = sorted([v for v in by_vms.keys() if v > 0])
    if not vm_sizes_sorted:
        return charts_html + "<p>No result folders found under this disk.</p>"

    vm_tabs_nav, vm_tabs_body = [], []
    for idx, vm_count in enumerate(vm_sizes_sorted):
        vm_id = f"{px_version}_{disk_name}_{vm_count}".replace(".", "_").replace("-", "_")
        active_cls = "active" if idx == 0 else ""
        show_cls = "show" if idx == 0 else ""
        vm_tabs_nav.append(
            f'<li class="nav-item"><button class="nav-link {active_cls}" id="tab-{vm_id}-tab" data-bs-toggle="tab" '
            f'data-bs-target="#tab_{vm_id}" type="button" role="tab">{vm_count} VMs</button></li>'
        )

        cb_sections = "".join(
            build_creation_boot_content(f, uid=f"{px_version}_{disk_name}_{vm_count}_{f.name}".replace(".", "_").replace("-", "_"))
            for f in by_vms[vm_count] if (f / "summary_vm_creation_results.json").exists()
        ) or "<p>No Creation/Boot Storm data for this VM size.</p>"

        mig_sections = "".join(
            build_migration_content(f, uid=f"{px_version}_{disk_name}_{vm_count}_{f.name}".replace(".", "_").replace("-", "_"))
            for f in by_vms[vm_count] if (f / "summary_migration_results.json").exists()
        ) or "<p>No Live Migration data for this VM size.</p>"

        vm_tabs_body.append(
            f"""
            <div class="tab-pane fade {show_cls} {active_cls}" id="tab_{vm_id}" role="tabpanel">
              <ul class="nav nav-pills mt-2" role="tablist">
                <li class="nav-item"><button class="nav-link active" id="tab-{vm_id}_cb-tab" data-bs-toggle="tab" data-bs-target="#tab_{vm_id}_cb" type="button" role="tab">Creation + Boot Storm</button></li>
                <li class="nav-item"><button class="nav-link" id="tab-{vm_id}_mig-tab" data-bs-toggle="tab" data-bs-target="#tab_{vm_id}_mig" type="button" role="tab">Live Migration</button></li>
              </ul>
              <div class="tab-content mt-3">
                <div class="tab-pane fade show active" id="tab_{vm_id}_cb" role="tabpanel">{cb_sections}</div>
                <div class="tab-pane fade" id="tab_{vm_id}_mig" role="tabpanel">{mig_sections}</div>
              </div>
            </div>
            """
        )

    return f"""
    {charts_html}
    <ul class="nav nav-tabs" role="tablist">{''.join(vm_tabs_nav)}</ul>
    <div class="tab-content mt-3">{''.join(vm_tabs_body)}</div>
    """


def build_px_tab(px_version: str, disk_map: dict) -> str:
    """Top-level PX version tab with disk subtabs."""
    disk_names = sorted(disk_map.keys(), key=lambda d: (int(d.split('-')[0]) if d.split('-')[0].isdigit() else 0, d))
    if not disk_names:
        return "<p>No disk groups found for this PX version.</p>"

    nav, body = [], []
    for idx, dname in enumerate(disk_names):
        did = f"{px_version}_{dname}".replace(".", "_").replace("-", "_")
        active_cls = "active" if idx == 0 else ""
        show_cls = "show" if idx == 0 else ""
        nav.append(f'<li class="nav-item"><button class="nav-link {active_cls}" id="tab-{did}-tab" data-bs-toggle="tab" data-bs-target="#tab_{did}" type="button" role="tab">{dname}</button></li>')
        body.append(f'<div class="tab-pane fade {show_cls} {active_cls}" id="tab_{did}" role="tabpanel">{build_disk_tab(px_version, dname, disk_map[dname])}</div>')

    return f"<ul class='nav nav-tabs mt-2' role='tablist'>{''.join(nav)}</ul><div class='tab-content mt-3'>{''.join(body)}</div>"


# ---------------- Main HTML ----------------
def build_html_page(px_nav, px_body):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>KubeVirt Performance Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
body {{ margin: 20px; }}
h3 {{ margin-top: 30px; }}
.dataTables_wrapper {{ width: 100%; margin: 0 auto; }}
table.dataTable {{ width: 100% !important; }}
</style>
</head>
<body>
<h1 class="mb-2">KubeVirt Performance Dashboard</h1>
<p><strong>Generated:</strong> {now}</p>

<ul class="nav nav-tabs" id="pxTab" role="tablist">{''.join(px_nav)}</ul>
<div class="tab-content" id="pxTabContent" style="margin-top: 1rem;">{''.join(px_body)}</div>

<script>
$(document).ready(function() {{
  $('table.display').DataTable({{ scrollX: true, autoWidth: false, pageLength: 25 }});

  $('a[data-bs-toggle="tab"], button[data-bs-toggle="tab"]').on('shown.bs.tab', function () {{
    $.fn.dataTable.tables({{visible: true, api: true}}).columns.adjust();
    setTimeout(function () {{
      document.querySelectorAll('.tab-pane.active .plotly-chart').forEach(function (el) {{
        try {{ Plotly.Plots.resize(el); }} catch(e) {{}}
      }});
    }}, 100);
  }});

  const topTabs = document.querySelectorAll('#pxTab .nav-link');
  if (topTabs.length > 0) {{
    const first = new bootstrap.Tab(topTabs[0]);
    first.show();
  }}

  setTimeout(function () {{
    document.querySelectorAll('.plotly-chart').forEach(function (el) {{
      try {{ Plotly.Plots.resize(el); }} catch(e) {{}}
    }});
  }}, 400);
}});
</script>
</body>
</html>
"""


# ---------------- Discover + Build ----------------
def main():
    parser = argparse.ArgumentParser(description="Generate KubeVirt Performance Dashboard (PX version → disk → Total VMs).")
    parser.add_argument("--days", type=int, default=15)
    parser.add_argument("--base-dir", type=str, default="results")
    parser.add_argument("--output-html", type=str, default="results_dashboard.html")
    parser.add_argument("--cluster-info", type=str, help="Path to cluster_info.yaml file", default=None)
    parser.add_argument("--manual-results", type=str, help="Path to manual_results.yaml file", default=None)

    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    cutoff = datetime.now() - timedelta(days=args.days)
    px_map = {}

    for px in sorted([d for d in base_dir.iterdir() if d.is_dir()]):
        disk_map = defaultdict(list)
        for disk_dir in sorted([d for d in px.iterdir() if d.is_dir()]):
            for run in sorted([r for r in disk_dir.iterdir() if r.is_dir()], key=lambda p: p.name):
                try:
                    ts = run.name.split("_")[0]
                    dt = datetime.strptime(ts, "%Y%m%d-%H%M%S")
                    if dt >= cutoff:
                        disk_map[disk_dir.name].append(run)
                except Exception:
                    continue
        if disk_map:
            px_map[px.name] = disk_map

    if not px_map:
        print("No results found within the timeframe.")
        return

    px_nav, px_body = [], []
    for idx, (px_version, disk_map) in enumerate(sorted(px_map.items())):
        px_id = f"px_{px_version}".replace(".", "_").replace("-", "_")
        active_cls = "active" if idx == 0 else ""
        show_cls = "show" if idx == 0 else ""
        px_nav.append(f'<li class="nav-item"><button class="nav-link {active_cls}" id="tab-{px_id}-tab" data-bs-toggle="tab" data-bs-target="#tab_{px_id}" type="button" role="tab">{px_version}</button></li>')
        px_body.append(f'<div class="tab-pane fade {show_cls} {active_cls}" id="tab_{px_id}" role="tabpanel">{build_px_tab(px_version, disk_map)}</div>')

    cluster_info = load_cluster_info(args.cluster_info) if args.cluster_info else None

    if cluster_info:
        cluster_html = build_cluster_info_tab(cluster_info)
        px_nav.append(
            '<li class="nav-item"><button class="nav-link" id="tab-clusterinfo-tab" data-bs-toggle="tab" data-bs-target="#tab_clusterinfo" type="button" role="tab">Cluster Info</button></li>')
        px_body.append(f'<div class="tab-pane fade" id="tab_clusterinfo" role="tabpanel">{cluster_html}</div>')

    manual_results = load_manual_results(args.manual_results) if args.manual_results else None
    if manual_results:
        manual_html = build_manual_results_tab(manual_results)
        px_nav.append(
            '<li class="nav-item"><button class="nav-link" id="tab-manualresults-tab" '
            'data-bs-toggle="tab" data-bs-target="#tab_manualresults" type="button" role="tab">Manual Results</button></li>'
        )
        px_body.append(f'<div class="tab-pane fade" id="tab_manualresults" role="tabpanel">{manual_html}</div>')

    out = Path(args.output_html)
    out.write_text(build_html_page(px_nav, px_body), encoding="utf-8")
    print(f"Dashboard generated: {out.absolute()}")


if __name__ == "__main__":
    main()
