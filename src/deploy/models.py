from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from .errors import ProjectValidationError

ProjectType = Literal["static_site", "redirect_site", "wsgi_site", "proxy", "custom", "go_site"]
SourceType = Literal["git", "local_git"]


@dataclass(frozen=True)
class BaseProject:
    name: str
    project_type: ProjectType
    hostname: str

    def to_record(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = data.pop("project_type")
        data["project"] = data.pop("name")
        return {key: value for key, value in data.items() if value is not None}


@dataclass(frozen=True)
class StaticSiteProject(BaseProject):
    source_type: SourceType
    source: str
    username: str
    project_dir: str
    home: str | None = None
    managed_user: bool = True
    managed_checkout: bool = True


@dataclass(frozen=True)
class RedirectSiteProject(BaseProject):
    to_hostname: str


@dataclass(frozen=True)
class WsgiSiteProject(BaseProject):
    source_type: SourceType
    source: str
    username: str
    project_dir: str
    home: str | None = None
    managed_user: bool = True
    managed_checkout: bool = True


@dataclass(frozen=True)
class ProxyProject(BaseProject):
    upstream_host: str
    upstream_port: int
    upstream_scheme: Literal["http", "https"] = "http"


@dataclass(frozen=True)
class CustomProject(BaseProject):
    config: bool = True


@dataclass(frozen=True)
class GoSiteProject(BaseProject):
    source_type: SourceType
    source: str
    username: str
    project_dir: str
    upstream_port: int
    home: str | None = None
    managed_user: bool = True
    managed_checkout: bool = True
    binary_name: str | None = None
    service_name: str | None = None


DeployProject = (
    StaticSiteProject
    | RedirectSiteProject
    | WsgiSiteProject
    | ProxyProject
    | CustomProject
    | GoSiteProject
)


def project_type_to_command_name(project_type: ProjectType) -> str:
    return project_type.replace("_", "-")


def command_name_to_project_type(name: str) -> ProjectType:
    normalized = name.replace("-", "_")
    if normalized not in {
        "static_site",
        "redirect_site",
        "wsgi_site",
        "proxy",
        "custom",
        "go_site",
    }:
        raise ProjectValidationError(f"unsupported project type: {name}")
    return normalized  # type: ignore[return-value]


def _require_str(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ProjectValidationError(f"missing or invalid field: {key}")
    return value


def _optional_str(record: dict[str, Any], key: str) -> str | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProjectValidationError(f"invalid field: {key}")
    return value


def _optional_bool(record: dict[str, Any], key: str) -> bool | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ProjectValidationError(f"invalid field: {key}")
    return value


def _managed_user_value(record: dict[str, Any]) -> bool:
    value = _optional_bool(record, "managed_user")
    if value is None:
        return False
    return value


def _managed_checkout_value(record: dict[str, Any]) -> bool:
    value = _optional_bool(record, "managed_checkout")
    if value is None:
        return False
    return value


def _project_dir_value(record: dict[str, Any]) -> str:
    project_dir = _optional_str(record, "project_dir")
    if project_dir:
        return project_dir
    legacy = _optional_str(record, "projectdir")
    if legacy and not _managed_checkout_value(record):
        return legacy
    if legacy and "source" not in record and "github" in record:
        return legacy
    if legacy:
        raise ProjectValidationError(
            "legacy field projectdir is only accepted for adopted or legacy "
            "source-backed projects; use project_dir in managed records"
        )
    return "checkout"


def _source_value(record: dict[str, Any]) -> str:
    source = _optional_str(record, "source")
    if source:
        return source
    github = _optional_str(record, "github")
    if github:
        return github
    raise ProjectValidationError("missing or invalid field: source")


def _source_type_value(record: dict[str, Any]) -> SourceType:
    source_type = _optional_str(record, "source_type")
    if source_type is None:
        source = _source_value(record)
        if source.startswith("/"):
            return "local_git"
        return "git"
    if source_type not in {"git", "local_git"}:
        raise ProjectValidationError("invalid field: source_type")
    return cast(SourceType, source_type)


def project_from_record(record: dict[str, Any], *, name: str | None = None) -> DeployProject:
    project_name = name or _require_str(record, "project")
    project_type = command_name_to_project_type(_require_str(record, "type"))
    hostname = _require_str(record, "hostname")

    if project_type == "static_site":
        return StaticSiteProject(
            name=project_name,
            project_type=project_type,
            hostname=hostname,
            source_type=_source_type_value(record),
            source=_source_value(record),
            username=_require_str(record, "username"),
            project_dir=_project_dir_value(record),
            home=_optional_str(record, "home"),
            managed_user=_managed_user_value(record),
            managed_checkout=_managed_checkout_value(record),
        )

    if project_type == "redirect_site":
        to_hostname = _optional_str(record, "to_hostname") or _optional_str(record, "to_hostame")
        if not to_hostname:
            raise ProjectValidationError("missing or invalid field: to_hostname")
        return RedirectSiteProject(
            name=project_name,
            project_type=project_type,
            hostname=hostname,
            to_hostname=to_hostname,
        )

    if project_type == "wsgi_site":
        return WsgiSiteProject(
            name=project_name,
            project_type=project_type,
            hostname=hostname,
            source_type=_source_type_value(record),
            source=_source_value(record),
            username=_require_str(record, "username"),
            project_dir=_project_dir_value(record),
            home=_optional_str(record, "home"),
            managed_user=_managed_user_value(record),
            managed_checkout=_managed_checkout_value(record),
        )

    if project_type == "custom":
        config = record.get("config")
        if config is not True:
            raise ProjectValidationError("missing or invalid field: config")
        return CustomProject(
            name=project_name,
            project_type=project_type,
            hostname=hostname,
            config=True,
        )

    if project_type == "go_site":
        upstream_port = record.get("upstream_port", record.get("port"))
        if not isinstance(upstream_port, int):
            raise ProjectValidationError("missing or invalid field: upstream_port")
        return GoSiteProject(
            name=project_name,
            project_type=project_type,
            hostname=hostname,
            source_type=_source_type_value(record),
            source=_source_value(record),
            username=_require_str(record, "username"),
            project_dir=_project_dir_value(record),
            upstream_port=upstream_port,
            home=_optional_str(record, "home"),
            managed_user=_managed_user_value(record),
            managed_checkout=_managed_checkout_value(record),
            binary_name=_optional_str(record, "binary_name"),
            service_name=_optional_str(record, "service_name"),
        )

    upstream_port = record.get("upstream_port", record.get("port"))
    if not isinstance(upstream_port, int):
        raise ProjectValidationError("missing or invalid field: upstream_port")
    upstream_host = _optional_str(record, "upstream_host") or "127.0.0.1"
    upstream_scheme = _optional_str(record, "upstream_scheme") or "http"
    if upstream_scheme not in {"http", "https"}:
        raise ProjectValidationError("invalid field: upstream_scheme")
    return ProxyProject(
        name=project_name,
        project_type=project_type,
        hostname=hostname,
        upstream_host=upstream_host,
        upstream_port=upstream_port,
        upstream_scheme=cast(Literal["http", "https"], upstream_scheme),
    )


def project_path(project_dir: Path, name: str) -> Path:
    return project_dir / name
