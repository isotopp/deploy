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


class AdoptPreflightError(DeployError):
    """Raised when an adopt operation cannot safely attach to existing state."""


class UpdatePreflightError(DeployError):
    """Raised when an update operation requires manual inspection/intervention."""


class ImportPreflightError(DeployError):
    """Raised when an import operation cannot safely replace project metadata."""
