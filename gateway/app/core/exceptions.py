class GatewayError(Exception):
    """Base exception for gateway errors."""


class GatewayAuthenticationError(GatewayError):
    """Raised when authentication fails."""


class GatewayAuthorizationError(GatewayError):
    """Raised when authorization fails."""


class InternalRouteBlockedError(GatewayError):
    """Raised when an internal route is requested through the gateway."""


class DownstreamServiceTimeoutError(GatewayError):
    """Raised when a downstream request times out."""


class DownstreamServiceUnavailableError(GatewayError):
    """Raised when a downstream service is unavailable."""
