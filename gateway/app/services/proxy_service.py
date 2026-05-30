from collections.abc import Mapping

import httpx
from fastapi import Request, Response

from app.core.config import get_settings
from app.core.exceptions import DownstreamServiceTimeoutError, DownstreamServiceUnavailableError
from app.core.logging import correlation_id_ctx

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


class GatewayProxyService:
    def __init__(
        self,
        *,
        base_urls: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
        transports: Mapping[str, httpx.AsyncBaseTransport] | None = None,
    ) -> None:
        settings = get_settings()
        self.base_urls = dict(
            base_urls
            or {
                "auth": settings.auth_service_base_url,
                "item": settings.item_service_base_url,
                "matching": settings.matching_service_base_url,
                "recovery": settings.recovery_case_service_base_url,
            },
        )
        self.timeout_seconds = timeout_seconds or settings.downstream_timeout_seconds
        self.transports = dict(transports or {})

    async def forward(
        self,
        request: Request,
        *,
        service_name: str,
        upstream_path: str,
    ) -> Response:
        headers = self._build_downstream_headers(request)
        body = await request.body()

        try:
            async with httpx.AsyncClient(
                base_url=self.base_urls[service_name],
                timeout=self.timeout_seconds,
                transport=self.transports.get(service_name),
                follow_redirects=False,
            ) as client:
                upstream_response = await client.request(
                    request.method,
                    upstream_path,
                    content=body or None,
                    params=list(request.query_params.multi_items()),
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise DownstreamServiceTimeoutError(
                f"Timeout ao chamar {service_name} em {upstream_path}",
            ) from exc
        except httpx.HTTPError as exc:
            raise DownstreamServiceUnavailableError(
                f"Falha ao chamar {service_name} em {upstream_path}: {exc}",
            ) from exc

        response_headers: dict[str, str] = {}
        content_type = upstream_response.headers.get("content-type")
        if content_type:
            response_headers["content-type"] = content_type

        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=response_headers,
        )

    def _build_downstream_headers(self, request: Request) -> dict[str, str]:
        headers: dict[str, str] = {}
        for header_name, header_value in request.headers.items():
            normalized_name = header_name.lower()
            if normalized_name in HOP_BY_HOP_HEADERS:
                continue
            if normalized_name in {"accept", "authorization", "content-type"}:
                headers[header_name] = header_value

        headers["X-Correlation-ID"] = request.headers.get(
            "X-Correlation-ID",
            correlation_id_ctx.get(),
        )
        return headers


def get_proxy_service() -> GatewayProxyService:
    return GatewayProxyService()
