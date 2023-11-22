#! /usr/bin/env python3
import argparse
import getpass
import json
import os
import pwd
import subprocess
import sys
from pathlib import Path

VALID_USERS = ["kris", "joram"]
VALID_OPERATIONS = ["code", "create", "delete", "logs"]
PROJECT_DIR = Path("/etc/projects")
CHECKOUT_CMD = "/usr/bin/git pull --rebase"
RESTART_CMD = "sudo apachectl stop; sleep 1; sudo apachectl start"

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
    parser.add_argument("--checkout-cmd", help="command to check out the source (in create, optional)")
    parser.add_argument("--restart-cmd", help="command to run after checkout (in create, optional)")
    args = parser.parse_args()


def show_run_result(result: subprocess.CompletedProcess):
    code = result.returncode
    if code == 0:
        print("*** SUCCESS:")
        print(result.stdout.decode('utf-8'))
        print(result.stderr.decode('utf-8'))
    else:
        print(f"*** ERROR: exit code={result.returncode}")
        print(result.stdout.decode('utf-8'))
        print(result.stderr.decode('utf-8'))
    print()


def deploy_code(project: str):
    p = PROJECT_DIR / project
    if not p.is_file():
        raise ValueError(f"cannot deploy to project {project}, no project file found.")

    config = load_deploy_description(project)
    os.chdir(config["projectdir"])

    deploy_cmd = f"sudo -u {config['unixuser']} {config['checkout_cmd']}"
    print(f"Running deploy_cmd {deploy_cmd}")

    deploy_result = subprocess.run(deploy_cmd, shell=True, capture_output=True, timeout=30)
    show_run_result(deploy_result)
    if (deploy_result.returncode != 0):
        print("*** DEPLOYMENT ABORTED ***")
        print("*** NO SERVICE RESTART ***")
        return

    restart_cmd = config['restart_cmd']
    print(f"Running restart_cmd {restart_cmd}")

    restart_result = subprocess.run(restart_cmd, shell=True, capture_output=True, timeout=30)
    show_run_result(restart_result)


def load_deploy_description(project: str) -> dict:
    p = PROJECT_DIR / project
    text = p.read_text()
    data = json.loads(text)

    return data


def create_deploy_description(project: str,
                              hostname: str,
                              unixuser: str,
                              projectdir: str,
                              checkout_cmd: str,
                              restart_cmd: str):
    if project is None or hostname is None or projectdir is None:
        raise ValueError("Missing options: specify --hostname, --unixuser and --projectdir.")

    if checkout_cmd is None:
        checkout_cmd = CHECKOUT_CMD

    if restart_cmd is None:
        restart_cmd = RESTART_CMD

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
        "checkout_cmd": checkout_cmd,
        "restart_cmd": restart_cmd,
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
        deploy_code(project=args.project)
    elif args.operation == "create":
        create_deploy_description(project=args.project,
                                  hostname=args.hostname,
                                  unixuser=args.unixuser,
                                  projectdir=args.projectdir,
                                  checkout_cmd=args.checkout_cmd,
                                  restart_cmd=args.restart_cmd)
    elif args.operation == "delete":
        delete_deployment_description(project=args.project)
    elif args.operation == "logs":
        pass
    else:
        raise ValueError(f"This can never happen: {args.operation=}")


if __name__ == "__main__":
    main()
