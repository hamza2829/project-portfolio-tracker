"""Self-contained static HTML and SVG, with no scripts or remote assets."""
from html import escape

from .schema import iso_date


def e(value):
    return escape(str(value), quote=True)


def timeline(metrics):
    projects = metrics["projects"]
    dates = [iso_date(row[field]) for row in projects for field in ["Start date", "Due date"]]
    first = min(dates, default=iso_date(metrics["as_of"]))
    last = max(dates, default=first)
    span = max(1, (last - first).days)

    def x(value):
        return 100 + 680 * (iso_date(value) - first).days / span

    parts = [f'<svg viewBox="0 0 820 {len(projects) * 30 + 48}" role="img" aria-label="Project milestone timeline">',
        f'<text x="100" y="14">{first.isoformat()}</text><text x="690" y="14">{last.isoformat()}</text>']
    for index, row in enumerate(projects):
        y = 28 + index * 30
        parts += [f'<text x="0" y="{y + 13}">{e(row["Project key"])}</text>',
            f'<rect x="{x(row["Start date"]):.1f}" y="{y}" width="{max(2, x(row["Due date"]) - x(row["Start date"])):.1f}" height="16" rx="4" fill="#c9d8ea"><title>{e(row["Project name"])}</title></rect>']
        for milestone in metrics["milestones"]:
            if milestone["Project key"] == row["Project key"]:
                color = "#c44450" if milestone["Delay days"] else "#13877c"
                parts.append(f'<circle cx="{x(milestone["Target date"]):.1f}" cy="{y + 8}" r="5" fill="{color}"><title>{e(milestone["Milestone key"])}: target {e(milestone["Target date"])}, {milestone["Delay days"]} days late</title></circle>')
    review_x = x(metrics["as_of"])
    parts += [f'<line x1="{review_x:.1f}" x2="{review_x:.1f}" y1="20" y2="{len(projects) * 30 + 22}" stroke="#243c59" stroke-dasharray="4 4"/>', "</svg>"]
    return "".join(parts)


def heatmap(portfolio, metrics):
    weeks = sorted({row["Week"] for row in metrics["workload"]})
    members = portfolio["members"]
    lookup = {(row["Assignee"], row["Week"]): row for row in metrics["workload"]}
    parts = [f'<svg viewBox="0 0 {max(600, 165 + len(weeks) * 46)} {len(members) * 35 + 52}" role="img" aria-label="Weekly workload heatmap">']
    for index, week in enumerate(weeks):
        parts.append(f'<text x="{165 + index * 46}" y="16" font-size="9">{week[5:]}</text>')
    for index, member in enumerate(members):
        y = 30 + index * 35
        parts.append(f'<text x="0" y="{y + 16}">{e(member["Display name"])} ({e(member["Weekly capacity hours"])}h)</text>')
        for column, week in enumerate(weeks):
            row = lookup.get((member["Account id"], week))
            utilization = row["Utilization"] if row else 0
            color = "#facccd" if utilization > 1 else "#d4e7e2" if utilization else "#edf1f6"
            value = f'{row["Planned hours"]:g}' if row else "0"
            x = 162 + column * 46
            parts += [f'<rect x="{x}" y="{y}" width="40" height="28" rx="4" fill="{color}"><title>{e(member["Display name"])} / {week}: {value} planned hours</title></rect>',
                f'<text x="{x + 20}" y="{y + 18}" text-anchor="middle">{value}</text>']
    return "".join(parts) + "</svg>"


def dashboard(portfolio, metrics):
    project_rows, risk_rows = [], []
    for row in metrics["projects"]:
        tone = "red" if row["Status"] == "Off track" else "amber" if row["Status"] == "At risk" else "green"
        project_rows.append(f'<tr><td><strong>{e(row["Project key"])}</strong><small>{e(row["Project name"])}</small></td><td>{e(row["Project lead"])}</td>'
            f'<td><div class="progress"><span style="width:{row["Progress percent"]}%"></span></div>{row["Progress percent"]:.1f}%</td>'
            f'<td><span class="badge {tone}">{row["Status"]}</span></td><td>{row["Milestone delay days"]} d</td><td>{row["Risk exposure"]:.1f}</td></tr>')
    for row in metrics["risks"]:
        risk_rows.append(f'<tr><td><strong>{e(row["Risk key"])}</strong><small>{e(row["Project key"])}</small></td><td>{e(row["Summary"])}</td><td>{e(row["Owner"])}</td><td>{e(row["Due date"])}</td><td>{row["Exposure"]:.2f}</td><td>{"Overdue" if row["Overdue"] else "Open"}</td></tr>')
    statuses = {state: sum(row["Status"] == state for row in metrics["projects"]) for state in ["On track", "At risk", "Off track"]}
    status_chart = '<svg viewBox="0 0 550 72" role="img" aria-label="Project status distribution">'
    offset = 0
    for state, color in [("On track", "#13877c"), ("At risk", "#bf7c22"), ("Off track", "#c44450")]:
        width = 500 * statuses[state] / max(1, len(metrics["projects"]))
        status_chart += f'<rect x="{offset}" y="6" width="{width}" height="20" fill="{color}"/><text x="{["On track", "At risk", "Off track"].index(state) * 180}" y="55">{state}: {statuses[state]}</text>'
        offset += width
    status_chart += "</svg>"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Department portfolio | {e(metrics['quarter'])}</title>
<style>
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#f0f4f9;color:#20334c;font:14px/1.55 Arial,sans-serif}}a{{color:inherit}}.sidebar{{position:fixed;inset:0 auto 0 0;width:220px;background:#152840;color:#d5e0ed;padding:36px 25px}}.brand{{font-size:19px;font-weight:700;letter-spacing:-.4px;color:white}}.brand span{{display:block;font-size:10px;letter-spacing:2px;color:#91b3cb;margin-top:5px}}.sidebar nav{{margin-top:48px}}.sidebar a{{display:block;text-decoration:none;padding:12px 10px;border-radius:6px;margin-bottom:6px}}.sidebar a:hover,.sidebar a:focus{{background:#28435f}}.sidebar p{{position:absolute;bottom:25px;font-size:11px;color:#9ab0c8;max-width:165px}}main{{margin-left:220px;padding:36px 38px;max-width:1640px}}header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px}}.eyebrow{{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:#647a92;font-weight:bold}}h1{{font-size:32px;letter-spacing:-1px;margin:5px 0}}header p{{margin:0;color:#60748c}}.stamp{{background:white;border:1px solid #d9e2ed;padding:9px 15px;border-radius:6px;font-size:12px}}.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:22px}}.kpi{{background:white;border:1px solid #dde5ef;border-radius:9px;padding:19px 22px}}.kpi b{{display:block;font-size:29px;color:#17334f;margin:5px 0}}.kpi span{{font-size:12px;color:#61758d}}.card{{background:white;border:1px solid #dde5ef;border-radius:10px;padding:24px;margin-bottom:22px;overflow:auto}}h2{{font-size:18px;margin:0 0 5px}}.sub{{color:#64788f;font-size:12px;margin:0 0 20px}}.grid{{display:grid;grid-template-columns:1.1fr 1fr;gap:22px}}table{{width:100%;border-collapse:collapse;font-size:12px}}th{{color:#667b92;font-size:10px;text-transform:uppercase;letter-spacing:.5px;text-align:left;background:#f7f9fc}}th,td{{padding:13px 12px;border-bottom:1px solid #e8edf4;vertical-align:middle}}td small{{display:block;font-size:11px;color:#6d8097;margin-top:3px}}.badge{{padding:5px 9px;border-radius:4px;font-size:10px;white-space:nowrap}}.red{{background:#fae5e6;color:#a3303a}}.amber{{background:#fff1d9;color:#8e5a13}}.green{{background:#e2f2ec;color:#146555}}.progress{{display:inline-block;width:68px;height:5px;background:#e8edf4;margin-right:8px;vertical-align:middle;border-radius:4px}}.progress span{{display:block;height:5px;background:#2e8b88;border-radius:4px}}svg{{display:block;width:100%;height:auto;font-family:Arial,sans-serif;font-size:12px;fill:#526983}}.recommendations{{margin:0;padding-left:18px;color:#4d627b}}.recommendations li{{margin:10px 0}}footer{{color:#6c8098;font-size:11px;padding:4px 0 22px}}@media(max-width:1050px){{.sidebar{{position:static;width:100%;padding:20px}}.sidebar nav,.sidebar p{{display:none}}main{{margin:0;padding:22px}}.grid{{grid-template-columns:1fr}}}}@media(max-width:650px){{.kpis{{grid-template-columns:repeat(2,1fr)}}header{{display:block}}.stamp{{display:inline-block;margin-top:15px}}}}
</style></head><body><aside class="sidebar"><div class="brand">Portfolio desk<span>DEPARTMENT PLANNING LAB</span></div><nav aria-label="Sections"><a href="#overview">Portfolio overview</a><a href="#timeline">Milestone timeline</a><a href="#workload">Team workload</a><a href="#risks">Open risks</a><a href="#decisions">Management decisions</a></nav><p>Synthetic data only.<br>No live Jira connection.<br>Planning snapshot, not live monitoring.</p></aside><main><header><div><div class="eyebrow">Quarterly review / {e(metrics['quarter'])}</div><h1>Department portfolio</h1><p>Plans, delivery risks and the decisions ahead.</p></div><div class="stamp">Snapshot {e(metrics['as_of'])}</div></header>
<section class="kpis" aria-label="Portfolio summary"><div class="kpi"><span>Active project plans</span><b>{len(metrics['projects'])}</b><span>{metrics['counts']['issues']} imported tasks</span></div><div class="kpi"><span>Delayed milestones</span><b>{sum(row['Delay days'] > 0 for row in metrics['milestones'])}</b><span>Targets requiring review</span></div><div class="kpi"><span>Overloaded person-weeks</span><b>{len(metrics['conflicts'])}</b><span>Planned demand above capacity</span></div><div class="kpi"><span>Open risk exposure</span><b>{metrics['risk_exposure']:.1f}</b><span>Probability x impact score</span></div></section>
<section id="overview" class="card"><h2>Project status</h2><p class="sub">Progress uses original and remaining effort. Status is calculated from milestone delay, blockers and risk exposure.</p>{status_chart}<table><thead><tr><th>Project</th><th>Lead</th><th>Progress</th><th>Status</th><th>Max delay</th><th>Risk score</th></tr></thead><tbody>{''.join(project_rows)}</tbody></table></section>
<div class="grid"><section id="timeline" class="card"><h2>Milestone timeline</h2><p class="sub">Bars: project plans. Dots: milestone targets. Red: delayed. Dashed line: review date.</p>{timeline(metrics)}</section><section id="decisions" class="card"><h2>Decisions for management</h2><p class="sub">{len(metrics['gaps'])} projects lack a recent update. {len(metrics['overdue_actions'])} actions are overdue.</p><ul class="recommendations">{''.join('<li>' + e(line) + '</li>' for line in metrics['recommendations'])}</ul></section></div>
<section id="workload" class="card"><h2>Weekly workload</h2><p class="sub">Planned hours per person. Red cells exceed that person's weekly capacity. Blank allocations count as zero planned hours.</p>{heatmap(portfolio, metrics)}</section>
<section id="risks" class="card"><h2>Open risks</h2><p class="sub">Sorted by probability x impact. Exposure is a score, not a financial forecast.</p><table><thead><tr><th>Risk</th><th>Description</th><th>Owner</th><th>Due</th><th>Exposure</th><th>Action status</th></tr></thead><tbody>{''.join(risk_rows)}</tbody></table></section><footer>Synthetic portfolio lab. All project and person names are fictional. Snapshot files contain no live integrations.</footer></main></body></html>'''
