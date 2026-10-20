#!/usr/bin/python3
"""Atomically create a per-run kubeconfig from a token file."""

import json
import os
import sys
import tempfile


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: write_kubeconfig.py TOKEN_FILE CA_FILE OUTPUT_FILE GROUP_ID", file=sys.stderr)
        return 64

    token_file, ca_file, output_file, group_id_text = sys.argv[1:]
    try:
        group_id = int(group_id_text)
    except ValueError:
        print("GROUP_ID must be numeric", file=sys.stderr)
        return 64

    with open(token_file, "r", encoding="ascii") as token_stream:
        token = token_stream.read().strip()
    if not token or "\n" in token or "\r" in token:
        raise ValueError("token file did not contain one token")

    config = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{
            "name": "local-k3s",
            "cluster": {
                "server": "https://127.0.0.1:6443",
                "certificate-authority": ca_file,
            },
        }],
        "users": [{"name": "capstone-deployer", "user": {"token": token}}],
        "contexts": [{
            "name": "voting",
            "context": {
                "cluster": "local-k3s",
                "user": "capstone-deployer",
                "namespace": "voting",
            },
        }],
        "current-context": "voting",
    }

    output_dir = os.path.dirname(output_file)
    fd, temporary_path = tempfile.mkstemp(prefix=".kubeconfig-", dir=output_dir)
    try:
        os.fchmod(fd, 0o640)
        os.fchown(fd, 0, group_id)
        with os.fdopen(fd, "w", encoding="utf-8") as output_stream:
            json.dump(config, output_stream, separators=(",", ":"))
            output_stream.write("\n")
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.replace(temporary_path, output_file)
        directory_fd = os.open(output_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
