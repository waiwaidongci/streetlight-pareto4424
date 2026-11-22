"""临汀市虚拟路灯台账与已归并的暗区事件。"""


_SITES = (
    ("滨河片区", "柳汀大道北段", 32, (14, 14, 15, 16, 17, 18, 19, 20)),
    ("老城片区", "东门巷", 5, (14, 16, 17, 19, 20)),
    ("滨河片区", "汀桥路公交站段", 24, (15, 17, 18, 20)),
    ("滨河片区", "长堤辅道", 3, (16, 20)),
    ("老城片区", "西仓里路口", 2, (19,)),
    ("滨河片区", "渡口支路", 9, ()),
    ("滨河片区", "桐浦堤下通道", 6, ()),
    ("老城片区", "埠头街南段", 14, ()),
    ("老城片区", "石平码头广场路", 11, ()),
    ("老城片区", "钟楼西街", 17, ()),
)

# 11 月 8–26 日工单批次：配合完工登记演示整治效果配对。LH-02 在 11-16 完工当日仍有一单，用于体现完工当日不计单。
_EFFECT_ORDERS = {
    "LH-01": (10, 11, 13, 14, 15, 16, 18, 20, 22, 24),
    "LH-02": (9, 10, 12, 13, 14, 15, 16, 19),
    "LH-03": (11, 14, 16, 19, 23),
    "LH-04": (10, 12, 13, 15, 16),
    "LH-05": (13, 15, 18, 20, 23),
    "LH-06": (13, 20),
    "LH-07": (),
    "LH-08": (10, 11, 12, 14, 17, 20, 22, 24),
    "LH-09": (11, 13, 14, 16, 17, 21, 25),
    "LH-10": (12, 14, 16, 18, 22, 24),
}

_COMPLETIONS = (
    ("ZG-2611-01", "LH-02", "2026-11-16"),
    ("ZG-2611-02", "LH-09", "2026-11-18"),
    ("ZG-2611-03", "LH-10", "2026-11-19"),
    ("ZG-2611-04", "LH-04", "2026-11-17"),
)


def _register_row(site_id, district, site, fixtures):
    return {
        "record_type": "灯组台账", "site_id": site_id, "district": district,
        "site_name": site, "fixture_count": fixtures, "incident_id": None, "report_date": None,
    }


def _incident_row(site_id, incident_id, report_date):
    return {
        "record_type": "暗区工单", "site_id": site_id, "district": None,
        "site_name": None, "fixture_count": None,
        "incident_id": incident_id, "report_date": report_date,
    }


def demo_rows() -> list[dict]:
    rows = []
    for number, (district, site, fixtures, days) in enumerate(_SITES, start=1):
        site_id = f"LH-{number:02d}"
        rows.append(_register_row(site_id, district, site, fixtures))
        for sequence, day in enumerate(days, start=1):
            rows.append(_incident_row(site_id, f"LT-2611{day}-{number:02d}-{sequence:02d}", f"2026-11-{day}"))
    return rows


def demo_effect_rows() -> list[dict]:
    rows = []
    for number, (district, site, fixtures, _days) in enumerate(_SITES, start=1):
        site_id = f"LH-{number:02d}"
        rows.append(_register_row(site_id, district, site, fixtures))
        for sequence, day in enumerate(_EFFECT_ORDERS[site_id], start=1):
            rows.append(_incident_row(site_id, f"LT-2611{day:02d}-{number:02d}-{sequence:02d}", f"2026-11-{day:02d}"))
    return rows


def demo_completion_rows() -> list[dict]:
    return [
        {"completion_id": completion_id, "site_id": site_id, "completion_date": day}
        for completion_id, site_id, day in _COMPLETIONS
    ]
