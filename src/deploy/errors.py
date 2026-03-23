class DeployError(Exception):
    """Base deploy error."""


class ProjectNotFoundError(DeployError):
    """Raised when a project definition does not exist."""


class ProjectValidationError(DeployError):
    """Raised when a project definition is invalid."""
