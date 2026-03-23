from deploy.errors import CommandExecutionError
from deploy.runner import CommandRunner
from deploy.runtime import ExecutionContext, RunMode


def test_live_runner_raises_on_command_failure() -> None:
    runner = CommandRunner(ExecutionContext(mode=RunMode.LIVE))

    try:
        runner.run(["false"])
    except CommandExecutionError as exc:
        assert "command failed" in str(exc)
    else:
        raise AssertionError("expected CommandExecutionError")
