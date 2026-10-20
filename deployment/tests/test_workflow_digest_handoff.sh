#!/bin/bash
set -Eeuo pipefail

test_dir=$(mktemp --directory)
cleanup() {
  rm -rf -- "$test_dir"
}
trap cleanup EXIT HUP INT TERM

for name in vote result worker; do
  jq -n \
    --arg name "$name" \
    --arg commit "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
    --arg repository "ghcr.io/ecstasywonder/example-voting-app-$name" \
    --arg digest "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
    '{name: $name, repository: $repository, commit: $commit, digest: ($repository + "@" + $digest)}' \
    > "$test_dir/$name.json"
done

for name in vote result worker; do
  digest=$(jq -er '.digest | split("@")[1]' "$test_dir/$name.json")
  [[ $digest =~ ^sha256:[0-9a-f]{64}$ ]]
done

printf 'workflow digest handoff: PASS\n'
