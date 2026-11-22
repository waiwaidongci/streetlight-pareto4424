from datetime import date
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.models.source import Completion


def snapshot(db):
    """读取当前完工登记，作为运行发起时固化的快照。"""
    rows = db.scalars(select(Completion).order_by(Completion.completion_date, Completion.completion_id, Completion.id))
    return [{"completion_id": row.completion_id, "site_id": row.site_id,
             "completion_date": row.completion_date.isoformat()} for row in rows]


def add_rows(db, records, actor):
    """把校验过的完工登记追加到登记册，完工单号重复的跳过。"""
    added = skipped = 0
    for record in records:
        try:
            with db.begin_nested():
                db.add(Completion(completion_id=record["completion_id"], site_id=record["site_id"],
                                  completion_date=date.fromisoformat(record["completion_date"]), author=actor))
                db.flush()
            added += 1
        except IntegrityError:
            skipped += 1
    return added, skipped
