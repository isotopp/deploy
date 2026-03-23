class DeployError(Exception):
    """Base deploy error."""


class ProjectNotFoundError(DeployError):
    """Raised when a project definition does not exist."""


class ProjectValidationError(DeployError):
    """Raised when a project definition is invalid."""


class CommandExecutionError(DeployError):
    """Raised when a subprocess command fails."""


class CreatePreflightError(DeployError):
    """Raised when a create operation is not safe to start."""
