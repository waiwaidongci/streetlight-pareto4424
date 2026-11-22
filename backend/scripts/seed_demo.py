import json
from sqlalchemy import func, select
from src.config.database import Session
from src.constants.enums import Role
from src.domain.demo import demo_completion_rows, demo_effect_rows, demo_rows
from src.domain.spec import SPEC
from src.models.identity import User
from src.models.source import Completion, Dataset
from src.services.completions import add_rows
from src.services.datasets import save
from src.utils.security import hash_password


def seed():
    with Session.begin() as db:
        for role in Role:
            if not db.get(User, role.value):
                db.add(User(username=role.value, role=role, password_hash=hash_password(f'{role.value}-demo-2611')))
        effect, _ = save(db, SPEC['effect_dataset'], SPEC['effect_sample'], demo_effect_rows(), 'seed')
        item, created = save(db, SPEC['default_dataset'], SPEC['sample_name'], demo_rows(), 'seed')
        completions, skipped = add_rows(db, demo_completion_rows(), 'seed')
        return {'users': db.scalar(select(func.count()).select_from(User)),
                'datasets': db.scalar(select(func.count()).select_from(Dataset)),
                'seed_dataset_id': item.id, 'row_count': item.row_count, 'checksum': item.checksum,
                'created_dataset': created, 'effect_dataset_id': effect.id,
                'completions': db.scalar(select(func.count()).select_from(Completion)),
                'seeded_completions': completions, 'skipped_completions': skipped}


if __name__ == '__main__':
    print(json.dumps(seed(), ensure_ascii=False))
