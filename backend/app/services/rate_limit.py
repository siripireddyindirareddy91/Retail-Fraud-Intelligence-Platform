import time
from datetime import timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..core.errors import APIError
from ..core.security import digest
from ..models import RateBucket, now


def enforce(db, key: str, maximum: int, seconds=900):
    window = int(time.time()) // seconds
    bucket = digest(f"{key}:{window}")
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    statement = insert(RateBucket).values(key=bucket, count=1, expires_at=now() + timedelta(seconds=seconds))
    statement = statement.on_conflict_do_update(index_elements=[RateBucket.key], set_={"count": RateBucket.count + 1}).returning(RateBucket.count)
    count = db.execute(statement).scalar_one()
    db.commit()
    if count > maximum:
        raise APIError(429, "rate_limited", "Too many requests. Please try again later.", headers={"Retry-After": str(seconds - int(time.time()) % seconds)})


def client_key(request):
    # Forwarded headers are deliberately ignored; configure trusted proxy handling at Uvicorn.
    return request.client.host if request.client else "unknown"
