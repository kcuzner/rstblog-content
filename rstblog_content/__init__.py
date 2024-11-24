import argparse
import subprocess
import requests


def test():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--branch", help="Specify a branch other than the one currently checked out"
    )
    parser.add_argument("--port", default=3000, type=int, help="Host port to use")
    parser.add_argument(
        "--app-path", default="app", help="Path to the app relative to the server root"
    )

    args = parser.parse_args()

    branch = (
        args.branch
        if args.branch
        else subprocess.check_output(["git", "symbolic-ref", "HEAD"])
        .decode("utf-8")
        .strip()
        .removeprefix("refs/heads/")
    )
    if branch == "(unnamed branch)":
        raise Exception(
            "Ensure that a branch is properly checked out befor running this script"
        )
    url = f"http://localhost:{args.port}/{args.app_path}"
    print(
        f"Attempting to refresh local rstblog running at {url} with latest commit on {branch}"
    )
    try:
        r = requests.get(f"{url}/test", {"branch": branch})
        r.raise_for_status()
    except:
        print("Testing the blog has failed. Please ensure that:")
        print(" * rstblog is cloned next door to this repository")
        print(" * rstblog settings are configured for (only critical settings shown):")
        print("   [repository]")
        print("   url=/repo")
        print("   [server]")
        print("   port=3000")
        print(" * rstblog has a docker-compose.override.yml with:")
        print("   services:")
        print("     worker:")
        print("       volumes:")
        print("         - type: bind")
        print("           source: ../rstblog-content")
        print("           target: /repo")
        print(
            " * You have used rstblog's ./run_interactive.sh script to start the server locally"
        )
        print(" * There were no errors reported in the log")
        raise
