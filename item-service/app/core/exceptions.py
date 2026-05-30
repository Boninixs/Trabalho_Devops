class ItemServiceError(Exception):
    """Base exception for item-service."""


class ItemNotFoundError(ItemServiceError):
    """Raised when an item cannot be found."""


class InvalidItemTransitionError(ItemServiceError):
    """Raised when a status transition is not allowed."""


class InvalidItemUpdateError(ItemServiceError):
    """Raised when a patch request is invalid."""

