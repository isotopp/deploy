#! /usr/bin/env python
import argparse
import getpass
import json
import pwd
import sys
from pathlib import Path

VALID_USERS = ["kris", "joram"]
VALID_OPERATIONS = ["code", "create", "delete", "logs"]
PROJECT_DIR = Path("projects")

args: argparse.Namespace


def can_do() -> str:
    """ Deployments can be done by one of the users listed in VALID USERS.
        We raise a ValueError if we are being run by somebody else.
    """
    user = getpass.getuser()
    if user in VALID_USERS:
        return user

    raise ValueError(f"invalid user {user}, valid users are: {VALID_USERS}")


def operation(the_op: str) -> str:
    """ ArgumentParser validator for the positional parameter operation.
        Valid operations are in VALID_OPERATIONS.
        We raise a ValueError for anything else.
    """
    if the_op in VALID_OPERATIONS:
        return the_op

    raise ValueError


def get_opts():
    """ Parse the program options using ArgumentParser.
        The collected arguments are left in a global variable args.
    """
    global args

    parser = argparse.ArgumentParser()
    parser.add_argument("operation", type=operation, help="code, create, delete or logs")
    parser.add_argument("project", help="a valid project name")

    parser.add_argument("--hostname", help="hostname (in create)")
    parser.add_argument("--unixuser", help="unixuser (in create)")
    parser.add_argument("--projectdir", help="projectdir (in create)")

    args = parser.parse_args()


def create_deploy_description(project: str, hostname: str, unixuser: str, projectdir: str):
    if project is None or hostname is None or projectdir is None:
        raise ValueError("Missing options: specify --hostname, --unixuser and --projectdir.")

    # check the hostname
    if not hostname.endswith("snackbag.net"):
        raise ValueError(f"invalid hostname {hostname}, must end in 'snackbag.net'")

    # check the unixuser
    try:
        pwd.getpwnam(unixuser)
    except KeyError as e:
        raise KeyError(f"user {unixuser} does not exist.")

    # check the projectdir
    if not Path(projectdir).is_dir():
        raise ValueError(f"projectdir {projectdir} does not a directory")

    # to json
    deployment = {
        "hostname": hostname,
        "unixuser": unixuser,
        "projectdir": projectdir,
    }
    deployment_json = json.dumps(deployment, indent=2, sort_keys=True) + "\n"

    # write it
    p = PROJECT_DIR / project
    if p.is_file():
        print(f"Project {project} already exists.", file=sys.stderr)
        raise FileExistsError(f"can't create: project {project} exists.")

    with p.open("wt") as f:
        f.write(deployment_json)


def delete_deployment_description(project: str):
    p = PROJECT_DIR / project
    if not p.is_file():
        raise ValueError(f"cannot delete deployment {project}, no project file found.")

    p.unlink()


def main():
    # Check valid user, and grab the call options
    user = can_do()
    get_opts()

    # operation is one of the things in VALID_OPERATIONS
    if args.operation == "code":
        pass
    elif args.operation == "create":
        create_deploy_description(project=args.project, hostname=args.hostname, unixuser=args.unixuser,
                                  projectdir=args.projectdir)
    elif args.operation == "delete":
        delete_deployment_description(project=args.project)
    elif args.operation == "logs":
        pass
    else:
        raise ValueError(f"This can never happen: {args.operation=}")


if __name__ == "__main__":
    main()
