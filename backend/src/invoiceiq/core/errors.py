"""Domain errors and the API error envelope."""


class DomainError(Exception):
    """Base class for domain errors carrying an error code + http status."""

    code = "INTERNAL_ERROR"
    http_status = 500

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404


class UnauthorizedError(DomainError):
    code = "UNAUTHORIZED"
    http_status = 401


class ForbiddenError(DomainError):
    code = "FORBIDDEN"
    http_status = 403


class ValidationFailure(DomainError):
    code = "VALIDATION_ERROR"
    http_status = 422


class ConflictError(DomainError):
    code = "CONFLICT"
    http_status = 409


class RateLimitedError(DomainError):
    code = "RATE_LIMITED"
    http_status = 429


class ProcessingError(DomainError):
    """Raised when an invoice cannot be processed (OCR failure, corrupt file)."""

    code = "INVOICE_NOT_PROCESSABLE"
    http_status = 422
