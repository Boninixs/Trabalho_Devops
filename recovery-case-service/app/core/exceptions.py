class RecoveryCaseServiceError(Exception):
    """Base exception for recovery-case-service."""


class RecoveryCaseNotFoundError(RecoveryCaseServiceError):
    """Raised when a recovery case cannot be found."""


class RecoveryCaseConflictError(RecoveryCaseServiceError):
    """Raised when a recovery case violates domain integrity."""


class InvalidRecoveryCaseTransitionError(RecoveryCaseServiceError):
    """Raised when a recovery case transition is invalid."""


class ItemServiceIntegrationError(RecoveryCaseServiceError):
    """Raised when the item-service cannot complete a saga step."""
