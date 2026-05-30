from typing import Protocol

import httpx

from app.core.config import get_settings
from app.core.exceptions import ItemServiceIntegrationError
from app.schemas.item_service import (
    ItemRecoveryCancelRequest,
    ItemRecoveryCompleteRequest,
    ItemRecoveryOpenRequest,
    ItemRecoveryOperationResponse,
)


class ItemRecoveryClient(Protocol):
    def open_recovery(self, payload: ItemRecoveryOpenRequest) -> ItemRecoveryOperationResponse: ...

    def cancel_recovery(self, payload: ItemRecoveryCancelRequest) -> ItemRecoveryOperationResponse: ...

    def complete_recovery(self, payload: ItemRecoveryCompleteRequest) -> ItemRecoveryOperationResponse: ...


class HttpItemRecoveryClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.item_service_base_url
        self.timeout_seconds = timeout_seconds or settings.item_service_timeout_seconds
        self.transport = transport

    def open_recovery(self, payload: ItemRecoveryOpenRequest) -> ItemRecoveryOperationResponse:
        return self._post("/internal/recovery/open", payload.model_dump(mode="json"))

    def cancel_recovery(self, payload: ItemRecoveryCancelRequest) -> ItemRecoveryOperationResponse:
        return self._post("/internal/recovery/cancel", payload.model_dump(mode="json"))

    def complete_recovery(self, payload: ItemRecoveryCompleteRequest) -> ItemRecoveryOperationResponse:
        return self._post("/internal/recovery/complete", payload.model_dump(mode="json"))

    def _post(self, path: str, payload: dict) -> ItemRecoveryOperationResponse:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.post(path, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ItemServiceIntegrationError(f"Falha ao chamar item-service em {path}: {exc}") from exc

        return ItemRecoveryOperationResponse.model_validate(response.json())


def get_item_recovery_client() -> ItemRecoveryClient:
    return HttpItemRecoveryClient()
