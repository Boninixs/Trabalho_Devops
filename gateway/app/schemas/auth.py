from uuid import UUID

from pydantic import BaseModel


class GatewayTokenClaims(BaseModel):
    sub: UUID
    role: str
    exp: int
