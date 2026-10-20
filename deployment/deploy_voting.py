#!/usr/bin/python3
"""Deploy the trusted main revision using a namespace-only Kubernetes token."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import BinaryIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPOSITORY = "ecstasywonder/example-voting-app"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/commits/main"
ARCHIVE_URL = f"https://codeload.github.com/{REPOSITORY}/tar.gz"
HELM = "/usr/local/bin/helm"
K3S = "/usr/local/bin/k3s"
NAMESPACE = "voting"
RELEASE = "voting"
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
MAX_API_BYTES = 1 * 1024 * 1024
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_MEMBERS = 10_000
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_MEMBER_BYTES = 256 * 1024 * 1024


class DeploymentError(RuntimeError):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def read_limited(response: BinaryIO, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, limit + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise DeploymentError("HTTP response exceeded its size limit")


def open_fixed_https(url: str, expected_host: str, *, accept: str):
    request = Request(url, headers={
        "Accept": accept,
        "User-Agent": "ts-capstone-private-k3s-deployer/1",
    })
    response = urlopen(request, timeout=30)
    if response.status != 200:
        response.close()
        raise DeploymentError(f"unexpected HTTP status {response.status}")
    final_url = response.geturl()
    if final_url.split("/", 3)[:3] != ["https:", "", expected_host]:
        response.close()
        raise DeploymentError("HTTPS request was redirected away from its fixed host")
    return response


def require_current_main(commit_sha: str) -> None:
    with open_fixed_https(API_URL, "api.github.com", accept="application/vnd.github+json") as response:
        payload = read_limited(response, MAX_API_BYTES)
    try:
        document = json.loads(payload)
        current_sha = document["sha"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise DeploymentError("GitHub main response was invalid") from error
    if not isinstance(current_sha, str) or not COMMIT_PATTERN.fullmatch(current_sha):
        raise DeploymentError("GitHub main response did not contain a full commit SHA")
    if current_sha != commit_sha:
        raise DeploymentError("requested commit is no longer the repository main commit")
    log(f"source guard accepted current main commit {commit_sha}")


def download_archive(commit_sha: str, archive_path: Path) -> str:
    digest = hashlib.sha256()
    total = 0
    url = f"{ARCHIVE_URL}/{commit_sha}"
    with open_fixed_https(url, "codeload.github.com", accept="application/x-gzip") as response:
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                if int(content_length) > MAX_ARCHIVE_BYTES:
                    raise DeploymentError("source archive advertised an excessive size")
            except ValueError as error:
                raise DeploymentError("source archive had an invalid Content-Length") from error
        with archive_path.open("xb") as archive_stream:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise DeploymentError("source archive exceeded its size limit")
                digest.update(chunk)
                archive_stream.write(chunk)
    archive_digest = digest.hexdigest()
    log(f"downloaded source commit={commit_sha} archive_sha256={archive_digest}")
    return archive_digest


def _validated_parts(name: str, expected_root: str) -> tuple[str, ...]:
    if not name or name.startswith("/"):
        raise DeploymentError("archive contains an empty or absolute path")
    path = PurePosixPath(name)
    if any(part in ("", ".", "..") for part in path.parts):
        raise DeploymentError("archive contains a non-canonical path")
    if not path.parts or path.parts[0] != expected_root:
        raise DeploymentError("archive contains a path outside the expected commit root")
    return path.parts


def safe_extract_selected(archive_path: Path, destination: Path, commit_sha: str) -> tuple[Path, Path]:
    expected_root = f"example-voting-app-{commit_sha}"
    chart_prefix = (expected_root, "helm", "voting-app")
    test_parts = (expected_root, "result", "tests", "tests.py")
    selected_names: set[tuple[str, ...]] = set()
    total_size = 0

    try:
        # Streaming mode enforces member and expansion limits before the whole
        # gzip archive can be parsed into memory or a large member list.
        with tarfile.open(archive_path, mode="r|gz") as archive:
            member_count = 0
            for member in archive:
                member_count += 1
                if member_count > MAX_MEMBERS:
                    raise DeploymentError("source archive contains too many members")
                parts = _validated_parts(member.name.rstrip("/"), expected_root)
                if member.size < 0 or member.size > MAX_MEMBER_BYTES:
                    raise DeploymentError("source archive contains an oversized member")
                total_size += member.size
                if total_size > MAX_TOTAL_MEMBER_BYTES:
                    raise DeploymentError("source archive expands beyond its total size limit")

                selected = parts[: len(chart_prefix)] == chart_prefix or parts == test_parts
                if not selected:
                    continue
                if parts in selected_names:
                    raise DeploymentError("source archive contains a duplicate selected path")
                selected_names.add(parts)
                if not (member.isdir() or member.isreg()):
                    raise DeploymentError("selected source contains a link or special file")

                relative_parts = parts[1:]
                target = destination.joinpath(*relative_parts)
                if member.isdir():
                    target.mkdir(mode=0o700, parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise DeploymentError("selected regular file had no archive data")
                try:
                    with target.open("xb") as output:
                        shutil.copyfileobj(source, output, length=64 * 1024)
                finally:
                    source.close()
                target.chmod(0o600)
    except (tarfile.TarError, OSError) as error:
        raise DeploymentError("source archive is not a valid gzip tar archive") from error

    chart_path = destination / "helm" / "voting-app"
    test_path = destination / "result" / "tests" / "tests.py"
    for required in (chart_path / "Chart.yaml", chart_path / "values.yaml", test_path):
        if not required.is_file():
            raise DeploymentError(f"source archive is missing required file {required.name}")
    return chart_path, test_path


def run(
    command: list[str], *, stdin: BinaryIO | None = None, capture: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess:
    log("running: " + " ".join(command))
    return subprocess.run(
        command,
        stdin=stdin,
        check=True,
        text=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        timeout=timeout,
    )


def previous_deployed_revision() -> int | None:
    command = [HELM, "history", RELEASE, "--namespace", NAMESPACE, "--output", "json"]
    log("checking prior Helm revisions")
    result = subprocess.run(
        command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
    )
    if result.returncode != 0:
        if "release: not found" in result.stderr.lower():
            return None
        raise DeploymentError("Helm history failed: " + result.stderr.strip())
    try:
        history = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise DeploymentError("Helm history returned invalid JSON") from error
    if not isinstance(history, list):
        raise DeploymentError("Helm history JSON was not a list")

    deployed: list[int] = []
    for entry in history:
        if not isinstance(entry, dict):
            raise DeploymentError("Helm history contained an invalid entry")
        revision = entry.get("revision")
        status = entry.get("status")
        if not isinstance(revision, int) or not isinstance(status, str):
            raise DeploymentError("Helm history omitted revision or status")
        if status.lower() == "deployed":
            deployed.append(revision)
    return max(deployed) if deployed else None


def helm_value_arguments(commit_sha: str, digests: tuple[str, str, str]) -> list[str]:
    arguments: list[str] = []
    for component, digest in zip(("vote", "result", "worker"), digests, strict=True):
        arguments.extend(["--set-string", f"{component}.image.tag={commit_sha}"])
        arguments.extend(["--set-string", f"{component}.image.digest={digest}"])
    return arguments


def deploy(commit_sha: str, digests: tuple[str, str, str]) -> None:
    require_current_main(commit_sha)
    with tempfile.TemporaryDirectory(prefix="run-", dir=os.getcwd()) as temporary_name:
        temporary = Path(temporary_name)
        archive_path = temporary / "source.tar.gz"
        download_archive(commit_sha, archive_path)
        source_path = temporary / "source"
        source_path.mkdir(mode=0o700)
        chart_path, test_path = safe_extract_selected(archive_path, source_path, commit_sha)

        previous_revision = previous_deployed_revision()
        value_arguments = helm_value_arguments(commit_sha, digests)
        run([HELM, "lint", str(chart_path), *value_arguments], timeout=30)
        # A newer main commit may have landed while the fixed archive was retrieved.
        # This check is intentionally adjacent to the mutating Helm command.
        require_current_main(commit_sha)
        run([
            HELM, "upgrade", "--install", RELEASE, str(chart_path),
            "--namespace", NAMESPACE,
            "--wait", "--timeout", "3m", "--rollback-on-failure",
            *value_arguments,
        ], timeout=210)

        try:
            with test_path.open("rb") as test_stream:
                run([
                    K3S, "kubectl", "--namespace", NAMESPACE,
                    "exec", "-i", "deployment/vote", "--", "python", "-",
                ], stdin=test_stream, timeout=90)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as original_error:
            if previous_revision is None:
                raise DeploymentError(
                    "end-to-end test failed after the first install; no prior revision exists to roll back"
                ) from original_error
            log(f"end-to-end test failed; rolling back to revision {previous_revision}")
            try:
                run([
                    HELM, "rollback", RELEASE, str(previous_revision),
                    "--namespace", NAMESPACE, "--wait", "--timeout", "2m",
                ], timeout=130)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as rollback_error:
                raise DeploymentError(
                    f"end-to-end test failed and rollback to revision {previous_revision} also failed"
                ) from rollback_error
            raise DeploymentError(
                f"end-to-end test failed; release rolled back to revision {previous_revision}"
            ) from original_error

        run([HELM, "status", RELEASE, "--namespace", NAMESPACE])
        log(f"deployment complete commit={commit_sha} result_digest={digests[1]}")


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: deploy-voting COMMIT_SHA VOTE_DIGEST RESULT_DIGEST WORKER_DIGEST", file=sys.stderr)
        return 64
    commit_sha = sys.argv[1]
    digests = (sys.argv[2], sys.argv[3], sys.argv[4])
    if not COMMIT_PATTERN.fullmatch(commit_sha):
        print("invalid commit SHA", file=sys.stderr)
        return 64
    if any(not DIGEST_PATTERN.fullmatch(digest) for digest in digests):
        print("invalid image digest", file=sys.stderr)
        return 64
    try:
        deploy(commit_sha, digests)
    except (
        DeploymentError, HTTPError, URLError, OSError,
        subprocess.CalledProcessError, subprocess.TimeoutExpired,
    ) as error:
        print(f"deployment failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
