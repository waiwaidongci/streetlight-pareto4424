import csv
import io
from urllib.parse import quote
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from src.config.database import connection
from src.constants.enums import Role
from src.controllers.auth import allow, current
from src.domain.demo import demo_completion_rows
from src.domain.spec import SPEC
from src.models.identity import User
from src.models.source import Completion
from src.schemas.requests import CompletionUpload
from src.services.audit import record
from src.services.completions import add_rows
from src.services.validation import parse_completion_rows
from src.utils import views

router = APIRouter(prefix='/completions')


@router.get('')
def index(db: Session = Depends(connection), actor: User = Depends(current)):
    rows = db.scalars(select(Completion).order_by(
        Completion.completion_date.desc(), Completion.completion_id.desc(), Completion.id.desc()).limit(1000))
    return [views.completion(row) for row in rows]


@router.get('/template')
def template(actor: User = Depends(current)):
    fields = [field['key'] for field in SPEC['completion_fields']]
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    # 模板附带演示登记，可直接作为导入样例。
    writer.writerows(demo_completion_rows())
    filename = quote(SPEC['completion_sample'])
    return Response('\ufeff' + buffer.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f"attachment; filename*=UTF-8''{filename}"})


@router.post('', status_code=201)
def upload(body: CompletionUpload, db: Session = Depends(connection),
           actor: User = Depends(allow(Role.ADMIN, Role.ANALYST))):
    records = parse_completion_rows(body.csv_text)
    added, skipped = add_rows(db, records, actor.username)
    if added:
        record(db, actor.username, 'completion.imported', 'completions', added=added, skipped=skipped)
    db.commit()
    total = db.scalar(select(func.count()).select_from(Completion))
    return {'added': added, 'skipped': skipped, 'total': total}
