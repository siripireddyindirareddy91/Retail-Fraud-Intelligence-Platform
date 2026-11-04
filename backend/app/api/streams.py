import asyncio
from datetime import timedelta
import json
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update

from .deps import CurrentUser, DB, owned
from ..models import AuthSession, MLModel, Notification, Prediction, StreamEvent, StreamSession, User, now
from ..research.data import FEATURES, generate
from ..research.ml import scores
from ..research.schemas import Generation, StreamConfig
from ..research.storage import read_bundle, records
from ..services.rate_limit import enforce

router = APIRouter(prefix="/streams", tags=["Simulated transaction streams"])


@router.post("", status_code=201)
def start_stream(payload: StreamConfig, request: Request, user: CurrentUser, db: DB):
    if payload.model_id:
        owned(db, MLModel, payload.model_id, user.id)
    enforce(db, f"stream:{user.id}", 10, 60)
    stream = StreamSession(owner_id=user.id, model_id=str(payload.model_id) if payload.model_id else None, config=payload.model_dump(mode="json"), expires_at=now() + timedelta(hours=2))
    db.add(stream)
    db.commit()
    return {"id": stream.id, "state": stream.state, "simulated": True}


@router.post("/{stream_id}/stop")
def stop_stream(stream_id: UUID, user: CurrentUser, db: DB):
    stream = owned(db, StreamSession, stream_id, user.id)
    stream.state = "stopped"
    db.commit()
    return {"id": stream.id, "state": stream.state}


@router.get("/{stream_id}")
def stream_state(stream_id: UUID, user: CurrentUser, db: DB):
    stream = owned(db, StreamSession, stream_id, user.id)
    rows = db.scalars(select(StreamEvent).where(StreamEvent.stream_id == stream.id).order_by(StreamEvent.id.desc()).limit(100)).all()
    return {"id": stream.id, "state": stream.state, "generated_count": stream.generated_count, "config": stream.config, "items": [row.payload for row in rows]}


@router.get("/{stream_id}/events")
def stream_events(stream_id: UUID, request: Request, user: CurrentUser, db: DB, after: int = Query(0, ge=0), last_event_id: int | None = Header(None, ge=0)):
    stream = owned(db, StreamSession, stream_id, user.id)
    owner_id, auth_id, config = user.id, request.state.auth_session_id, stream.config
    settings, sessions = request.app.state.settings, request.app.state.sessions
    model = db.get(MLModel, stream.model_id) if stream.model_id else None
    bundle = read_bundle(db, settings, model.artifact_id) if model else None
    model_id = model.id if model else None
    db.rollback()
    token = request.headers["authorization"].split(" ", 1)[1]

    def produce():
        with sessions() as session:
            account, auth = session.get(User, owner_id), session.get(AuthSession, auth_id)
            if not account or not account.active or not auth or auth.revoked_at or auth.expires_at <= now():
                return "auth_expired"
            session.execute(update(StreamSession).where(StreamSession.id == str(stream_id)).values(generated_count=StreamSession.generated_count))
            current = session.get(StreamSession, str(stream_id))
            if current.state != "running" or current.expires_at <= now() or current.generated_count >= config["max_transactions"]:
                if current.state == "running":
                    current.state = "completed"
                    session.commit()
                return None
            index = current.generated_count
            pool = generate(Generation(rows=100, fraud_rate=config["fraud_rate"], seed=config["seed"] + index // 100))
            row = pool.iloc[index % 100].copy()
            row["transaction_id"] = f"LIVE-SIM-{str(stream_id)[:8]}-{index:06d}"
            payload = records(row.to_frame().T)[0]
            payload["observed_at"] = now().isoformat() + "Z"
            payload["simulated"] = True
            payload["ground_truth"] = int(row.is_fraud)
            payload["predicted_class"], payload["probability"], payload["anomaly_score"] = None, None, None
            if bundle:
                score = float(scores(bundle, pool.iloc[index % 100:index % 100 + 1])[0])
                predicted = int(score >= bundle["threshold"])
                anomaly = bundle["algorithm"] == "isolation_forest"
                prediction = Prediction(owner_id=owner_id, model_id=model_id, transaction_id=str(row.transaction_id), features={key: payload[key] for key in FEATURES}, probability=None if anomaly else score, anomaly_score=score if anomaly else None, predicted_class=predicted, ground_truth=int(row.is_fraud), risk="high" if predicted else "low")
                session.add(prediction)
                session.flush()
                payload.update(prediction_id=prediction.id, predicted_class=predicted, probability=prediction.probability, anomaly_score=prediction.anomaly_score, risk=prediction.risk)
                if predicted:
                    session.add(Notification(user_id=owner_id, severity="warning", message=f"Simulated high-risk transaction {row.transaction_id}"))
            event = StreamEvent(stream_id=str(stream_id), payload=payload)
            session.add(event)
            current.generated_count += 1
            session.flush()
            event_id = event.id
            session.commit()
            return event_id, payload

    async def events():
        from ..core.security import decode_access
        import jwt
        cursor = max(after, last_event_id or 0)
        # Replay saved events first; a reconnect does not erase monitoring history.
        with sessions() as session:
            saved = [(row.id, row.payload) for row in session.scalars(select(StreamEvent).where(StreamEvent.stream_id == str(stream_id), StreamEvent.id > cursor).order_by(StreamEvent.id))]
        for event_id, payload in saved:
            cursor = event_id
            yield f"id: {event_id}\nevent: transaction\ndata: {json.dumps(payload)}\n\n"
        while not await request.is_disconnected():
            try:
                decode_access(settings, token)
            except jwt.InvalidTokenError:
                yield 'event: auth_expired\ndata: {}\n\n'
                return
            event = await asyncio.to_thread(produce)
            if event == "auth_expired":
                yield 'event: auth_expired\ndata: {}\n\n'
                return
            if event is None:
                yield 'event: stopped\ndata: {}\n\n'
                return
            event_id, payload = event
            cursor = event_id
            yield f"id: {event_id}\nevent: transaction\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(config["interval_seconds"])
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
