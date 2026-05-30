from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.item import ItemStatus
from app.schemas.item import ItemCreateRequest, RecoveryCancelRequest


def test_item_create_request_rejects_invalid_classification() -> None:
    with pytest.raises(ValidationError):
        ItemCreateRequest(
            classification="UNKNOWN",
            title="Mochila preta",
            description="Mochila perdida no bloco A",
            category="Mochila",
            color="Preta",
            location_description="Bloco A",
            approximate_date=date(2026, 4, 10),
            reporter_user_id=uuid4(),
        )


def test_recovery_cancel_request_rejects_invalid_target_status() -> None:
    with pytest.raises(ValidationError):
        RecoveryCancelRequest(
            item_ids=[uuid4()],
            target_status=ItemStatus.RECOVERED,
        )
