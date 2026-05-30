from typing import Literal

from app.schemas.events import EventEnvelope
from app.schemas.recovery_case import RecoveryCaseEventPayload


class RecoveryCaseOpenedEnvelope(EventEnvelope):
    event_type: Literal["RecoveryCaseOpened"]
    payload: RecoveryCaseEventPayload


class RecoveryCaseCancelledEnvelope(EventEnvelope):
    event_type: Literal["RecoveryCaseCancelled"]
    payload: RecoveryCaseEventPayload


class RecoveryCaseCompletedEnvelope(EventEnvelope):
    event_type: Literal["RecoveryCaseCompleted"]
    payload: RecoveryCaseEventPayload
