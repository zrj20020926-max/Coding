class InfrastructureError(RuntimeError):
    """A transient dependency failure that must leave the stream message pending."""


class JudgeConfigurationError(RuntimeError):
    """A non-retryable problem/language configuration failure."""
