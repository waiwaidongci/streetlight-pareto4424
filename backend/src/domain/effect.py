"""夜巡整治效果：按完工登记快照与同片区对照灯组配对，测算少报单量。"""

from bisect import bisect_left, bisect_right
from datetime import date, timedelta
from fractions import Fraction

from .analysis import validate_rows
from .spec import SPEC

_REGISTER, _INCIDENT = SPEC["fields"][0]["options"]
# 配对边权偏移量：保证先配成最多对，再压平各对整治前单量差。须大于任何单条边权。
_BIG = 1_000_000

_PAIR_COLUMNS = (
    ("pair", "对次"), ("district", "片区"), ("site_id", "整治灯组"), ("site_name", "整治点位"),
    ("completion_date", "首次完工日"), ("pre_window", "前期窗口"), ("treated_pre", "整治前单量"),
    ("post_window", "后期窗口"), ("treated_post", "整治后单量"), ("control_id", "对照灯组"),
    ("control_name", "对照点位"), ("control_pre", "对照前单量"), ("control_post", "对照后单量"),
    ("diff", "少报差（单）"),
)
_UNMATCHED_COLUMNS = (
    ("site_id", "灯组编号"), ("site_name", "台账点位"), ("district", "片区"),
    ("completion_date", "首次完工日"), ("treated_pre", "前期单量"), ("treated_post", "后期单量"),
    ("reason", "未配对原因"),
)
_GAP_COLUMNS = (
    ("completion_id", "完工单号"), ("site_id", "灯组编号"), ("completion_date", "完工日期"),
    ("note", "说明"),
)


def validate_completion_rows(rows):
    """校验完工登记明细，返回单号与灯组编号大写、日期规范化的记录。"""
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError("完工登记为空，请先导入完工记录。")
    seen = set()
    records = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"第 {index} 条完工登记格式有误。")
        completion_id = str(row.get("completion_id") or "").strip().upper()
        site_id = str(row.get("site_id") or "").strip().upper()
        if not completion_id:
            raise ValueError(f"第 {index} 条完工登记的完工单号不能为空。")
        if not site_id:
            raise ValueError(f"完工单号「{completion_id}」的灯组编号不能为空。")
        if completion_id in seen:
            raise ValueError(f"完工单号「{completion_id}」重复。")
        try:
            day = date.fromisoformat(str(row.get("completion_date") or ""))
        except ValueError:
            raise ValueError(f"完工单号「{completion_id}」的完工日期须为有效的 YYYY-MM-DD 日期。") from None
        seen.add(completion_id)
        records.append({"completion_id": completion_id, "site_id": site_id,
                        "completion_date": day.isoformat()})
    return records


def _parameters(params):
    if not isinstance(params, dict):
        raise ValueError("整治效果测算参数格式有误。")
    options = {}
    for field in SPEC["effect_params"]:
        value = params.get(field["key"], field["default"])
        if type(value) is not int or not field["min"] <= value <= field["max"]:
            raise ValueError(f"「{field['label']}」须在 {field['min']} 至 {field['max']} 之间，并为整数。")
        options[field["key"]] = value
    return options


def _count(days, start, end):
    """在升序日期列表中统计 [start, end] 内的工单数。"""
    return bisect_right(days, end) - bisect_left(days, start)


def _match(treated, candidates):
    """二分配对：treated 为排序后的整治组，candidates 为 {整治组: [(对照组, 前单量差), ...]}。

    先配成最多对，再让各对差值之和最小。节点与边按固定顺序展开，结果可复现。
    """
    controls = sorted({control for edges in candidates.values() for control, _ in edges})
    if not treated or not controls:
        return []
    sink = 1 + len(treated) + len(controls)
    graph = [[] for _ in range(sink + 1)]

    def link(source, target, capacity, cost):
        graph[source].append([target, capacity, cost, len(graph[target])])
        graph[target].append([source, 0, -cost, len(graph[source]) - 1])

    control_node = {control: 1 + len(treated) + index for index, control in enumerate(controls)}
    for index, site in enumerate(treated):
        link(0, 1 + index, 1, 0)
        for control, gap in candidates.get(site, ()):
            link(1 + index, control_node[control], 1, gap - _BIG)
    for control in controls:
        link(control_node[control], sink, 1, 0)

    infinite = float("inf")
    while True:
        dist = [infinite] * (sink + 1)
        dist[0] = 0
        prev = [None] * (sink + 1)
        for _round in range(sink + 1):
            relaxed = False
            for node in range(sink + 1):
                if dist[node] == infinite:
                    continue
                for edge_index, edge in enumerate(graph[node]):
                    target, capacity, cost, _reverse = edge
                    if capacity and dist[node] + cost < dist[target]:
                        dist[target] = dist[node] + cost
                        prev[target] = (node, edge_index)
                        relaxed = True
            if not relaxed:
                break
        if prev[sink] is None or dist[sink] >= 0:
            break
        node = sink
        while node:
            source, edge_index = prev[node]
            edge = graph[source][edge_index]
            edge[1] -= 1
            graph[node][edge[3]][1] += 1
            node = source

    pairs = []
    for index, site in enumerate(treated):
        for target, capacity, _cost, _reverse in graph[1 + index]:
            if 1 + len(treated) <= target < sink and not capacity:
                pairs.append((site, controls[target - 1 - len(treated)]))
    return pairs


def _table(title, columns, rows):
    return {"title": title, "columns": [{"key": key, "label": label} for key, label in columns], "rows": rows}


def analyze_effect(rows, normalized_params, snapshot):
    """用数据批次的台账与工单，按发起时固化的完工登记快照测算整治效果。"""
    records = validate_rows(rows)
    options = _parameters(normalized_params)
    window = options["window_days"]
    registry = validate_completion_rows(snapshot)
    sites = {row["site_id"]: row for row in records if row["record_type"] == _REGISTER}
    days_by_site = {}
    for row in records:
        if row["record_type"] == _INCIDENT:
            days_by_site.setdefault(row["site_id"], []).append(date.fromisoformat(row["report_date"]))
    for days in days_by_site.values():
        days.sort()

    first_completion = {}
    for entry in registry:
        site, day = entry["site_id"], date.fromisoformat(entry["completion_date"])
        if site not in first_completion or day < first_completion[site]:
            first_completion[site] = day
    gaps = [entry for entry in registry if entry["site_id"] not in sites]
    treated = sorted(site for site in first_completion if site in sites)
    if not treated:
        raise ValueError("完工登记中的灯组均未出现在本批次台账中，请核对灯组编号或更换数据批次。")

    span, one_day = timedelta(days=window), timedelta(days=1)
    treated_info = {}
    for site in treated:
        completed = first_completion[site]
        pre_start, pre_end = completed - span, completed - one_day
        post_start, post_end = completed + one_day, completed + span
        days = days_by_site.get(site, [])
        treated_info[site] = {
            "completed": completed, "pre_start": pre_start, "pre_end": pre_end,
            "post_start": post_start, "post_end": post_end,
            "pre": _count(days, pre_start, pre_end), "post": _count(days, post_start, post_end),
        }

    candidates = {}
    for site in treated:
        info, district = treated_info[site], sites[site]["district"]
        edges = []
        for other in sorted(sites):
            if other == site or sites[other]["district"] != district:
                continue
            completed_other = first_completion.get(other)
            if completed_other is not None and completed_other <= info["post_end"]:
                continue  # 截至该对窗口末日已整治，不能作对照
            gap = abs(info["pre"] - _count(days_by_site.get(other, []), info["pre_start"], info["pre_end"]))
            edges.append((other, gap))
        candidates[site] = edges

    pairs = _match(treated, candidates)
    paired = dict(pairs)
    pair_rows, diffs = [], []
    ordered = sorted(pairs, key=lambda pair: (treated_info[pair[0]]["completed"], pair[0]))
    for rank, (site, control) in enumerate(ordered, start=1):
        info = treated_info[site]
        control_days = days_by_site.get(control, [])
        control_pre = _count(control_days, info["pre_start"], info["pre_end"])
        control_post = _count(control_days, info["post_start"], info["post_end"])
        diff = (info["pre"] - info["post"]) - (control_pre - control_post)
        diffs.append(diff)
        pair_rows.append({
            "pair": rank, "district": sites[site]["district"], "site_id": site,
            "site_name": sites[site]["site_name"], "completion_date": info["completed"].isoformat(),
            "pre_window": f"{info['pre_start']}–{info['pre_end']}", "treated_pre": info["pre"],
            "post_window": f"{info['post_start']}–{info['post_end']}", "treated_post": info["post"],
            "control_id": control, "control_name": sites[control]["site_name"],
            "control_pre": control_pre, "control_post": control_post, "diff": diff,
        })

    unmatched = []
    for site in treated:
        if site in paired:
            continue
        info = treated_info[site]
        reason = "同片区没有截至窗口末日仍未整治的灯组" if not candidates[site] else "同片区可用对照已配完"
        unmatched.append({
            "site_id": site, "site_name": sites[site]["site_name"], "district": sites[site]["district"],
            "completion_date": info["completed"].isoformat(),
            "treated_pre": info["pre"], "treated_post": info["post"], "reason": reason,
        })

    average = round(float(Fraction(sum(diffs), len(diffs))), 2) if diffs else None
    treated_drop = sum(treated_info[site]["pre"] - treated_info[site]["post"] for site in paired)
    control_shift = sum(
        _count(days_by_site.get(control, []), treated_info[site]["pre_start"], treated_info[site]["pre_end"])
        - _count(days_by_site.get(control, []), treated_info[site]["post_start"], treated_info[site]["post_end"])
        for site, control in pairs
    )
    gap_note = f"，{len(gaps)} 条登记未匹配台账" if gaps else ""
    headline = (f"{len(treated)} 组整治灯组中 {len(pairs)} 组配到同片区对照，平均每对少报 {average} 单。"
                if pairs else f"{len(treated)} 组整治灯组均未配到同片区对照。")
    tables = [
        _table("整治与对照配对明细", _PAIR_COLUMNS, pair_rows),
        _table("未配对整治组", _UNMATCHED_COLUMNS, unmatched),
    ]
    if gaps:
        tables.append(_table("未匹配台账的完工登记", _GAP_COLUMNS, [
            {**entry, "note": "灯组不在本批次台账，未参与本次测算"} for entry in gaps
        ]))
    return {
        "state": "warning" if unmatched else "ok",
        "headline": headline,
        "note": (f"完工登记快照 {len(registry)} 条 · 覆盖 {len(first_completion)} 组 · 前后各 {window} 天计单，"
                 f"完工当日不计。快照以运行发起时为准，晚到的完工记录需重新测算才会纳入。"),
        "metrics": [
            {"label": "整治灯组", "value": len(treated),
             "detail": f"完工登记 {len(registry)} 条，覆盖 {len(first_completion)} 组{gap_note}"},
            {"label": "成功配对", "value": len(pairs), "detail": "每个对照灯组全报告仅用一次"},
            {"label": "平均每对少报（单）", "value": average,
             "detail": "各对少报差的均值" if pairs else "无配对，未计算"},
            {"label": "配对整治组合计少报（单）", "value": treated_drop,
             "detail": f"对照组同期变化 {control_shift} 单"},
            {"label": "未配对整治组", "value": len(unmatched), "detail": "同片区可用对照不足"},
            {"label": "计单窗口（天）", "value": window, "detail": "首次完工日前后各计，完工当日不计"},
        ],
        "tables": tables,
        "charts": [
            {"title": "各对少报差（单）", "kind": "bar",
             "series": [{"label": f"对{row['pair']}", "value": row["diff"]} for row in pair_rows]},
        ] if pairs else [],
        "sections": [{"title": "配对口径与登记快照", "text": (
            "对照组取自同片区、截至该对窗口末日仍未整治的灯组，窗口末日之后才完工的灯组仍可作对照；"
            "每个对照灯组全报告只使用一次。配对先凑成最多对，再让各对整治前单量差绝对值之和最小。"
            "每对少报差＝（整治组前单量−后单量）−（对照组前单量−后单量）。"
            "本次测算沿用发起时的完工登记快照，之后晚到的登记只供重新测算；后台中断恢复也沿用同一快照。"
        )}],
    }
