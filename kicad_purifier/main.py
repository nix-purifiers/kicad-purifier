"""KICAD's normal application workflow with a frozen native extension profile."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def public_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("KiCad plugin repositories must use public HTTPS URLs")
    return url


def selection(project):
    value = json.loads((project / "kicad-purifier.json").read_text())
    if set(value) != {"plugins"} or not isinstance(value["plugins"], list):
        raise ValueError("kicad-purifier.json needs a plugins list")
    if any(
        not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]*", name)
        for name in value["plugins"]
    ):
        raise ValueError("invalid KICAD plugin identifier")
    if len(set(value["plugins"])) != len(value["plugins"]):
        raise ValueError("duplicate KICAD plugin")
    if len({name.replace(".", "_") for name in value["plugins"]}) != len(
        value["plugins"]
    ):
        raise ValueError(
            "KiCad plugin identifiers collide in the native Python namespace"
        )
    return value


def project_path(explicit):
    if explicit:
        return Path(explicit).resolve()
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "kicad-purifier.json").exists() or (
            parent / "kicad-purifier.lock.json"
        ).exists():
            return parent
    return current


def validate(project, lock):
    data = json.loads(lock.read_text())
    if data.get("version") != 1 or data.get("purifier") != "kicad":
        raise ValueError("unsupported KICAD lock")
    if data.get("sdk") != os.environ["KICAD_PURIFIER_SDK"]:
        raise ValueError("KICAD SDK changed; run kicad-purifier lock --update")
    if data.get("selection") != selection(project):
        raise ValueError("plugin selection changed; run kicad-purifier lock --update")
    return data


def realize(project, lock, target="environment", out_link=None):
    args = [
        "nix",
        "build",
        "--impure",
        "--file",
        os.environ["KICAD_PURIFIER_REALIZE"],
        "--argstr",
        "projectPath",
        str(project),
        "--argstr",
        "lockPath",
        str(lock),
        "--argstr",
        "target",
        target,
        "--json",
    ]
    args += ["--out-link", str(out_link)] if out_link else ["--no-link"]
    result = run(args, stdout=subprocess.PIPE, text=True)
    return Path(json.loads(result.stdout)[0]["outputs"]["out"])


def capture(project, lock):
    import base64
    import hashlib
    import time
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    requested = selection(project)
    with tempfile.TemporaryDirectory(prefix="kicad-purifier-") as temporary:
        root = Path(temporary)
        schema = os.environ["KICAD_PURIFIER_SCHEMA"]
        helper = os.environ["KICAD_PURIFIER_HELPER"]
        headers = {
            "User-Agent": "KiCad/" + os.environ["KICAD_PURIFIER_NATIVE_VERSION"],
            "Accept": "application/vnd.kicad.pcm.v2+json",
        }

        def download(url, target):
            # KiCad's public endpoint serves this official GitLab repository.
            # The API is an alternate transport for the same published files.
            origin = "https://gitlab.com/api/v4/projects/kicad%2Faddons%2Frepository/repository/files/"
            mirrors = {
                "https://repository.kicad.org/repository.json": origin
                + "repository.json/raw?ref=main",
                "https://gitlab.com/kicad/addons/repository/-/raw/main/packages.json": origin
                + "packages.json/raw?ref=main",
            }
            routes = [url, mirrors.get(url, url), mirrors.get(url, url)]
            for attempt, route in enumerate(routes):
                try:
                    with urlopen(
                        Request(public_url(route), headers=headers), timeout=15
                    ) as response:
                        target.write_bytes(response.read())
                    return
                except (URLError, TimeoutError) as error:
                    if isinstance(error, HTTPError) and error.code not in {
                        403,
                        429,
                        500,
                        502,
                        503,
                        504,
                    }:
                        raise
                    if attempt == 2:
                        raise
                    print(f"retrying KiCad catalog download: {error}", file=sys.stderr)
                    time.sleep(attempt + 1)

        catalog = {}
        available = {}
        if requested["plugins"]:
            repository = root / "repository.json"
            download("https://repository.kicad.org/repository.json", repository)
            native_repository = json.loads(
                run(
                    [helper, "repository", str(repository), schema],
                    stdout=subprocess.PIPE,
                    text=True,
                ).stdout
            )
            packages = root / "packages.json"
            download(native_repository["packages"]["url"], packages)
            if (
                hashlib.sha256(packages.read_bytes()).hexdigest()
                != native_repository["packages"]["sha256"]
            ):
                raise ValueError(
                    "official KiCad package catalog hash changed during capture"
                )
            available = {
                item["id"]: item
                for item in json.loads(
                    run(
                        [helper, str(packages), schema],
                        stdout=subprocess.PIPE,
                        text=True,
                    ).stdout
                )
            }
            catalog = {
                item["identifier"]: item
                for item in json.loads(packages.read_text())["packages"]
            }
        entries = []
        for name in sorted(requested["plugins"]):
            if name not in available or catalog[name]["type"] != "plugin":
                raise ValueError(f"unknown KiCad code plugin: {name}")
            version = next(
                (
                    item["metadata"]
                    for item in available[name]["versions"]
                    if item["compatible"] and item["metadata"]["status"] == "stable"
                ),
                None,
            )
            if not version or version.get("runtime", "swig") != "swig":
                raise ValueError(
                    f"no compatible stable SWIG plugin: {name}; IPC needs a provider"
                )
            expected = (
                "sha256-"
                + base64.b64encode(bytes.fromhex(version["download_sha256"])).decode()
            )
            url = public_url(version["download_url"])
            fetched = json.loads(
                run(
                    [
                        "nix",
                        "store",
                        "prefetch-file",
                        "--json",
                        "--expected-hash",
                        expected,
                        url,
                    ],
                    stdout=subprocess.PIPE,
                    text=True,
                ).stdout
            )
            entries.append(
                {
                    "path": name,
                    "url": url,
                    "mirrors": [],
                    "hash": fetched["hash"],
                    "kicad": {"version": version["version"]},
                }
            )
        data = {
            "version": 1,
            "purifier": "kicad",
            "sdk": os.environ["KICAD_PURIFIER_SDK"],
            "selection": requested,
            "native": {
                "catalog": {name: catalog[name] for name in requested["plugins"]}
            },
            "entries": entries,
        }
        candidate = root / "kicad-purifier.lock.json"
        candidate.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        realize(project, candidate)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=lock.parent, delete=False
        ) as output:
            output.write(candidate.read_text())
            pending = Path(output.name)
        try:
            os.replace(pending, lock)
        finally:
            pending.unlink(missing_ok=True)


def native_exec(project, lock, arguments, command="kicad-python"):
    commands = Path(os.environ["KICAD_PURIFIER_COMMANDS"])
    if not lock.exists():
        print(
            "warning: no KiCad purifier lock; using ordinary, impure plugin resolution",
            file=sys.stderr,
        )
        original = (
            commands / command
            if command == "kicad-python"
            else Path(os.environ["KICAD_PURIFIER_ORIGINAL"]) / command
        )
        env = os.environ.copy()
        env.pop("KICAD_PURIFIER_ENVIRONMENT", None)
        os.execve(original, [str(original), *arguments], env)
    validate(project, lock)
    state = project / ".kicad-purifier"
    state.mkdir(exist_ok=True)
    environment = realize(project, lock, out_link=state / "environment")
    native = Path(os.environ["KICAD_PURIFIER_NATIVE"])
    settings = json.loads(
        run(
            [
                sys.executable,
                str(native / "kicad_purifier_prepare.py"),
                str(state),
                str(environment),
                os.environ["KICAD_PURIFIER_VERSION"],
            ],
            stdout=subprocess.PIPE,
            text=True,
        ).stdout
    )
    env = os.environ.copy() | settings
    executable = commands / command
    os.execve(executable, [str(executable), *arguments], env)


def main():
    if os.environ.get("KICAD_PURIFIER_COMMAND") in {
        "kicad",
        "pcbnew",
        "kicad-cli",
        "kicad-python",
    }:
        project = project_path(os.environ.get("KICAD_PURIFIER_PROJECT"))
        lock = Path(
            os.environ.get("KICAD_PURIFIER_LOCK", project / "kicad-purifier.lock.json")
        ).resolve()
        native_exec(project, lock, sys.argv[1:], os.environ["KICAD_PURIFIER_COMMAND"])
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--lock")
    sub = parser.add_subparsers(dest="action", required=True)
    lock_parser = sub.add_parser("lock")
    lock_parser.add_argument("--update", action="store_true")
    sub.add_parser("prefetch")
    for name in ["build", "bundle"]:
        sub.add_parser(name)
    publish = sub.add_parser("publish")
    publish.add_argument("--tag", required=True)
    execute = sub.add_parser("exec")
    execute.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    project = project_path(args.project or os.environ.get("KICAD_PURIFIER_PROJECT"))
    lock = Path(
        args.lock
        or os.environ.get("KICAD_PURIFIER_LOCK", project / "kicad-purifier.lock.json")
    ).resolve()
    if args.action == "lock" and args.update:
        capture(project, lock)
        return
    if args.action == "exec":
        arguments = (
            args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        )
        native_exec(project, lock, arguments)
        return
    validate(project, lock)
    if args.action == "lock":
        realize(project, lock)
    elif args.action == "prefetch":
        print(realize(project, lock))
    elif args.action in {"build", "bundle"}:
        print(
            realize(project, lock, "project" if args.action == "build" else "release")
        )
    elif args.action == "publish":
        release = realize(project, lock, "release")
        run(
            [
                os.environ.get("KICAD_PURIFIER_GH", "gh"),
                "release",
                "upload",
                args.tag,
                str(release / "kicad-project.tar.gz"),
                "--clobber",
            ]
        )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"kicad-purifier: {error}", file=sys.stderr)
        sys.exit(1)
