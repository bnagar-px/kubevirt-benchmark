#!/usr/bin/env python3
"""
Generate an interactive HTML dashboard for KubeVirt performance test results.

Supports:
  VM Creation + Boot Storm results
  Live Migration results

Each tab corresponds to one test folder (e.g., 20251016-154549_live_migration_kubevirt-perf-test_1-50)
and shows:
  - Results Directory
  - Total VMs
  - Duration summary (Creation / Boot Storm / Migration)
  - Per-VM results as sortable DataTables

Adds:
  - Overall Performance Summary section at the top with three compact bar charts:
    * Creation Duration (minutes)
    * Boot Storm Duration (minutes)
    * Live Migration Duration (minutes)

Usage:
  python3 generate_dashboard.py [--days N] [--base-dir PATH] [--output-html FILE]
"""

import json
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta


# ---------------- Utility Functions ----------------
def load_json(path):
    """Safely load JSON file."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def get_test_folders(base_dir, days=15):
    """Return a list of timestamped test folders under base_dir/ within last X days."""
    cutoff = datetime.now() - timedelta(days=days)
    folders = []
    for p in base_dir.iterdir():
        if not p.is_dir() or "-" not in p.name:
            continue
        try:
            timestamp_str = p.name.split("_")[0]
            folder_time = datetime.strptime(timestamp_str, "%Y%m%d-%H%M%S")
            if folder_time >= cutoff:
                folders.append(p)
        except Exception:
            continue
    return sorted(folders, key=lambda p: p.name)


def rename_metrics(metric_name):
    mapping = {
        "running_time_sec": "Running Time",
        "ping_time_sec": "Ping Time",
        "clone_duration_sec": "Clone Duration",
        "observed_time_sec": "Observed Time",
        "vmim_time_sec": "VMIM Time",
        "difference_observed_vmim_sec": "Difference (Observed - VMIM)",
    }
    return mapping.get(metric_name, metric_name)


def format_folder_name(folder_name):
    """
    Convert folder name like:
    '20251014-165952_kubevirt-perf-test_1-50'
    → '2025-10-14 16:59:52 — 50 VMs'
    """
    try:
        parts = folder_name.split("_")
        timestamp = parts[0]
        vm_range = parts[-1]
        dt = datetime.strptime(timestamp, "%Y%m%d-%H%M%S")

        # Extract start and end numbers
        if "-" in vm_range:
            start_str, end_str = vm_range.split("-")
            start = int(start_str)
            end = int(end_str)
            num_vms = (end - start) + 1
        else:
            num_vms = int(vm_range)

        suffix = "VM" if num_vms == 1 else "VMs"
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} — {num_vms} {suffix}"

    except Exception as e:
        print(f"[WARN] Failed to parse folder name '{folder_name}': {e}")
        return folder_name


def df_to_html_table(df, table_id):
    if df.empty:
        return f"<p>No data found for {table_id}</p>"
    return df.to_html(classes="display compact nowrap", table_id=table_id, index=False, border=0)


def summary_to_df(summary_json):
    """
    Convert a summary JSON into a DataFrame for display.
    Removes 'difference_observed_vmim_sec' and total VM info from the table,
    returning them separately to display below.
    """
    if not summary_json or "metrics" not in summary_json:
        return pd.DataFrame(), None, None

    rows = []
    difference_row = None

    for m in summary_json["metrics"]:
        metric_name = m["metric"]

        # Skip difference row
        if metric_name == "difference_observed_vmim_sec":
            difference_row = m
            continue

        # Normal metrics
        rows.append({
            "Metric": rename_metrics(metric_name),
            "Average (s)": m.get("avg"),
            "Max (s)": m.get("max"),
            "Min (s)": m.get("min"),
            "Count": m.get("count", ""),
        })

    df = pd.DataFrame(rows)

    # Extract total VM info separately
    total_vms = summary_json.get("total_vms")
    successful = summary_json.get("successful")
    failed = summary_json.get("failed")

    total_info = {
        "total_vms": total_vms,
        "successful": successful,
        "failed": failed
    }

    return df, difference_row, total_info


def plotly_chart(df, div_id, title):
    if df.empty:
        return f"<p>No summary data for {title}</p>"
    chart_data = df[df["Metric"].isin([
        "Running Time", "Ping Time", "Clone Duration",
        "Observed Time", "VMIM Time"
    ])]
    if chart_data.empty:
        return ""
    js_data = chart_data.to_dict(orient="list")
    return f"""
    <div id="{div_id}" style="height:300px;"></div>
    <script>
    Plotly.newPlot('{div_id}', [{{
        x: {js_data['Metric']},
        y: {js_data['Average (s)']},
        type: 'bar',
        marker: {{color: 'rgb(26, 118, 255)'}}
    }}], {{title: '{title}', yaxis: {{title: 'Seconds'}}}});
    </script>
    """


# ---------------- Overall Summary Section ----------------
def build_global_summary_section(test_folders):
    """
    Build overall summary charts for Creation, Boot Storm, and Live Migration.
    Each chart shows Total Duration (in minutes) vs Total VMs across folders.
    """
    summary_data = {"creation": [], "bootstorm": [], "migration": []}

    # --- Extract duration info from summaries ---
    for folder in test_folders:
        folder_path = Path(folder)
        folder_name = folder_path.name

        creation_summary = load_json(folder_path / "summary_vm_creation_results.json")
        boot_summary = load_json(folder_path / "summary_boot_storm_results.json")
        migration_summary = load_json(folder_path / "summary_migration_results.json")

        # Creation
        if creation_summary and creation_summary.get("total_test_duration_sec"):
            vms = creation_summary.get("total_vms", 0)
            duration_min = creation_summary["total_test_duration_sec"] / 60
            summary_data["creation"].append({"VMs": vms, "Minutes": round(duration_min, 2), "Folder": folder_name})

        # Boot Storm
        if boot_summary and boot_summary.get("total_test_duration_sec"):
            vms = boot_summary.get("total_vms", 0)
            duration_min = boot_summary["total_test_duration_sec"] / 60
            summary_data["bootstorm"].append({"VMs": vms, "Minutes": round(duration_min, 2), "Folder": folder_name})

        # Migration
        if migration_summary and (
            migration_summary.get("total_migration_duration_sec")
            or migration_summary.get("total_test_duration_sec")
        ):
            vms = migration_summary.get("total_vms", 0)
            total_time = migration_summary.get("total_migration_duration_sec") or migration_summary.get("total_test_duration_sec")
            duration_min = total_time / 60
            summary_data["migration"].append({"VMs": vms, "Minutes": round(duration_min, 2), "Folder": folder_name})

    # --- Chart helper ---
    def create_bar_chart(records, title, color, chart_id):
        if not records:
            return f"<div class='col'><p>No data for {title}</p></div>"
        df = pd.DataFrame(records).sort_values("VMs")
        x_values = df["VMs"].tolist()
        y_values = df["Minutes"].tolist()
        labels = df["Folder"].tolist()

        return f"""
        <div class="col-md-4">
          <div id="{chart_id}" style="height:350px;"></div>
          <script>
          Plotly.newPlot('{chart_id}', [{{
              x: {x_values},
              y: {y_values},
              text: {labels},
              type: 'bar',
              marker: {{
                  color: '{color}',
                  line: {{color: 'rgb(8,48,107)', width: 1.5}}
              }},
              hovertemplate: 'Folder: %{{text}}<br>VMs: %{{x}}<br>Duration: %{{y:.2f}} min<extra></extra>'
          }}], {{
              title: '{title}',
              xaxis: {{
                  title: 'Total VMs',
                  type: 'category'  // ✅ ensures only actual values appear
              }},
              yaxis: {{
                  title: 'Duration (minutes)'
              }},
              margin: {{t: 50, l: 50, r: 20, b: 50}},
              bargap: 0.3
          }});
          </script>
        </div>
        """

    # --- Build HTML Row with 3 Charts ---
    html = """
    <div class="container mt-4">
      <h2>Overall Performance Summary</h2>
      <div class="row text-center mt-3">
    """
    html += create_bar_chart(summary_data["creation"], "Creation Duration (minutes)", "rgb(26,118,255)", "chart_creation_summary")
    html += create_bar_chart(summary_data["bootstorm"], "Boot Storm Duration (minutes)", "rgb(0,204,150)", "chart_bootstorm_summary")
    html += create_bar_chart(summary_data["migration"], "Live Migration Duration (minutes)", "rgb(255,99,71)", "chart_migration_summary")

    html += """
      </div>
      <hr>
    </div>
    """
    return html


# ---------------- Folder Rendering ----------------
def build_folder_tab(folder: Path):
    """Build HTML content for one folder (test run)."""
    # (Unchanged existing logic)
    is_live_migration = "live_migration" in folder.name.lower()
    has_creation = (folder / "vm_creation_results.json").exists()
    has_bootstorm = (folder / "boot_storm_results.json").exists()

    # Determine test type label
    if is_live_migration:
        test_type = "Live Migration"
    elif has_creation and has_bootstorm:
        test_type = "Creation + Boot Storm"
    elif has_creation:
        test_type = "Creation"
    else:
        test_type = "Unknown"

    # --- Load JSON summaries ---
    creation_summary = load_json(folder / "summary_vm_creation_results.json") if not is_live_migration else None
    boot_summary = load_json(folder / "summary_boot_storm_results.json") if not is_live_migration else None
    migration_summary = load_json(folder / "summary_migration_results.json") if is_live_migration else None

    # --- Load detailed results ---
    creation_results = load_json(folder / "vm_creation_results.json") if not is_live_migration else None
    boot_results = load_json(folder / "boot_storm_results.json") if not is_live_migration else None
    migration_results = load_json(folder / "migration_results.json") if is_live_migration else None

    # --- Convert to DataFrames ---
    creation_df = pd.DataFrame(creation_results or [])
    boot_df = pd.DataFrame(boot_results or [])
    migration_df = pd.DataFrame(migration_results or [])

    creation_summary_df, creation_diff_row, creation_total_info = summary_to_df(creation_summary)
    boot_summary_df, boot_diff_row, boot_total_info = summary_to_df(boot_summary)
    migration_summary_df, migration_diff_row, migration_total_info = summary_to_df(migration_summary)

    # Ensure safe defaults (avoid NoneType)
    creation_total_info = creation_total_info or {}
    boot_total_info = boot_total_info or {}
    migration_total_info = migration_total_info or {}

    # Adjust columns
    if not creation_df.empty and "success" in creation_df.columns:
        cols = [c for c in creation_df.columns if c != "success"] + ["success"]
        creation_df = creation_df[cols]
    if not migration_df.empty and "status" in migration_df.columns:
        cols = [c for c in migration_df.columns if c != "status"] + ["status"]
        migration_df = migration_df[cols]

    folder_id = folder.name.replace("-", "_")
    folder_title = f"{format_folder_name(folder.name)} ({test_type})"

    # --- Basic info ---
    total_vms = (
        migration_total_info.get("total_vms") if is_live_migration and migration_total_info
        else creation_total_info.get("total_vms") if creation_total_info
        else "?"
    )
    total_vms_html = f"<h5><strong>Total VMs:</strong> {total_vms}</h5>"
    results_dir_html = f"<h5><strong>Results Directory:</strong> {folder.name}</h5>"

    # --- Durations ---
    creation_total_time = creation_summary.get("total_test_duration_sec") if creation_summary else None
    boot_total_time = boot_summary.get("total_test_duration_sec") if boot_summary else None
    migration_total_time = (
        migration_summary.get("total_migration_duration_sec")
        or migration_summary.get("total_test_duration_sec")
        if migration_summary
        else None
    )

    creation_duration_html = (
        f"<h5><strong>Total Creation Duration:</strong> {creation_total_time:.2f} s</h5>"
        if creation_total_time else ""
    )
    boot_duration_html = (
        f"<h5><strong>Total Boot Storm Duration:</strong> {boot_total_time:.2f} s</h5>"
        if boot_total_time else ""
    )
    migration_duration_html = (
        f"<h5><strong>Total Migration Duration:</strong> {migration_total_time:.2f} s</h5>"
        if migration_total_time else ""
    )

    # --- Convert tables ---
    creation_summary_html = df_to_html_table(creation_summary_df, f"table_summary_creation_{folder_id}")
    boot_summary_html = df_to_html_table(boot_summary_df, f"table_summary_boot_{folder_id}")
    migration_summary_html = df_to_html_table(migration_summary_df, f"table_summary_migration_{folder_id}")

    creation_html = df_to_html_table(creation_df, f"table_creation_{folder_id}")
    boot_html = df_to_html_table(boot_df, f"table_boot_{folder_id}")
    migration_html = df_to_html_table(migration_df, f"table_migration_{folder_id}")

    # --- Charts ---
    creation_chart = plotly_chart(creation_summary_df, f"chart_creation_{folder_id}", "VM Creation Average Times")
    boot_chart = plotly_chart(boot_summary_df, f"chart_boot_{folder_id}", "Boot Storm Average Times")
    migration_chart = plotly_chart(migration_summary_df, f"chart_migration_{folder_id}", "Migration Average Times")

    # --- Build HTML per test type (unchanged) ---
    if is_live_migration:
        diff_line = (
            f"<p><strong>Average Difference (Observed - VMIM):</strong> "
            f"{migration_diff_row.get('avg', 'N/A')} s</p>" if migration_diff_row else ""
        )
        totals_line = (
            f"<p><strong>Total VMs:</strong> {migration_total_info.get('total_vms', 'N/A')} | "
            f"<strong>Successful:</strong> {migration_total_info.get('successful', 'N/A')} | "
            f"<strong>Failed:</strong> {migration_total_info.get('failed', 'N/A')}</p>"
        )

        tab_html = f"""
        <div class="tab-pane fade" id="tab_{folder_id}" role="tabpanel">
            {results_dir_html}
            {total_vms_html}
            {migration_duration_html}

            <h3 class="mt-4">Migration Summary</h3>
            {migration_summary_html}
            {totals_line}
            {diff_line}
            {migration_chart}

            <h3 class="mt-5">Migration Results (Per VM)</h3>
            {migration_html}
        </div>
        """
    else:
        creation_totals = (
            f"<p><strong>Total VMs:</strong> {creation_total_info.get('total_vms', 'N/A')} | "
            f"<strong>Successful:</strong> {creation_total_info.get('successful', 'N/A')} | "
            f"<strong>Failed:</strong> {creation_total_info.get('failed', 'N/A')}</p>"
        )
        boot_totals = (
            f"<p><strong>Total VMs:</strong> {boot_total_info.get('total_vms', 'N/A')} | "
            f"<strong>Successful:</strong> {boot_total_info.get('successful', 'N/A')} | "
            f"<strong>Failed:</strong> {boot_total_info.get('failed', 'N/A')}</p>"
        )

        tab_html = f"""
        <div class="tab-pane fade" id="tab_{folder_id}" role="tabpanel">
            {results_dir_html}
            {total_vms_html}
            {creation_duration_html}
            {boot_duration_html}

            <h3 class="mt-4">Creation Summary</h3>
            {creation_summary_html}
            {creation_totals}
            {creation_chart}

            <h3 class="mt-5">Boot Storm Summary</h3>
            {boot_summary_html}
            {boot_totals}
            {boot_chart}

            <h3 class="mt-5">Creation Results</h3>
            {creation_html}

            <h3 class="mt-5">Boot Storm Results</h3>
            {boot_html}
        </div>
        """

    nav_html = (
        f'<li class="nav-item" role="presentation">'
        f'<button class="nav-link" id="tab-{folder_id}-tab" '
        f'data-bs-toggle="tab" data-bs-target="#tab_{folder_id}" type="button" role="tab">'
        f'{folder_title}</button></li>'
    )

    return tab_html, nav_html


# ---------------- HTML Page Builder ----------------
def build_html_page(test_tabs_html, test_tabs_nav):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>KubeVirt Performance Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
body {{
  margin: 20px;
}}
h3 {{
  margin-top: 30px;
}}
.dataTables_wrapper {{
  width: 100%;
  margin: 0 auto;
}}
table.dataTable {{
  width: 100% !important;
}}
</style>
</head>
<body>
<h1 class="mb-4">KubeVirt Performance Dashboard</h1>
<p><strong>Generated:</strong> {now}</p>

{test_tabs_html[0]}

<ul class="nav nav-tabs" id="myTab" role="tablist">
{''.join(test_tabs_nav)}
</ul>

<div class="tab-content" id="myTabContent">
{''.join(test_tabs_html[1:])}
</div>

<script>
$(document).ready(function() {{
    $('table.display').DataTable({{
        scrollX: true,
        autoWidth: false,
        pageLength: 25
    }});
    $('button[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {{
        $.fn.dataTable.tables({{ visible: true, api: true }}).columns.adjust();
    }});
    const allTabs = document.querySelectorAll('.nav-link');
    if (allTabs.length > 0) {{
        const lastTab = new bootstrap.Tab(allTabs[allTabs.length - 1]);
        lastTab.show();
    }}
}});
</script>
</body>
</html>
"""


# ---------------- Main ----------------
def main():
    parser = argparse.ArgumentParser(description="Generate KubeVirt Performance Dashboard")
    parser.add_argument("--days", type=int, default=15, help="Include folders from the last X days (default: 15)")
    parser.add_argument("--base-dir", type=str, default="results", help="Base directory containing test result folders (default: results/)")
    parser.add_argument("--output-html", type=str, default="results_dashboard.html", help="Path to save generated HTML file (default: results_dashboard.html)")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    output_html = Path(args.output_html)

    test_folders = get_test_folders(base_dir, days=args.days)
    if not test_folders:
        print(f"No test folders found in {base_dir} from the last {args.days} days.")
        return

    # Build overall summary charts
    overall_summary_html = build_global_summary_section(test_folders)

    tabs_html, tabs_nav = [], []
    for folder in test_folders:
        print(f"Processing folder: {folder.name}")
        tab_html, nav_html = build_folder_tab(folder)
        tabs_html.append(tab_html)
        tabs_nav.append(nav_html)

    # Inject summary section at the top
    tabs_html.insert(0, overall_summary_html)

    html = build_html_page(tabs_html, tabs_nav)
    output_html.write_text(html, encoding="utf-8")
    print(f"\nDashboard generated: {output_html.absolute()}")


if __name__ == "__main__":
    main()
