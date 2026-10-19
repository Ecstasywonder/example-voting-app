# Continuous Integration

`.github/workflows/ci.yml` runs on every push and pull request using GitHub-hosted `ubuntu-24.04` runners. It does not use a self-hosted runner or require repository secrets.

The pipeline first starts the existing Compose end-to-end suite from `result/docker-compose.test.yml`. It uses a unique Compose project name, saves container logs as an artifact when a test fails, and always removes the test containers and volumes.

Each application image is then built for `linux/amd64` and scanned with Trivy. Any HIGH or CRITICAL operating-system or library vulnerability fails the workflow. The report for every image is uploaded as a short-lived workflow artifact, including when the scan fails. No Trivy ignore file or ignored-unfixed setting is used.

Pull requests only test, build, and scan. They do not log in to a registry, receive `packages: write`, or push images. For a push, the scanned Docker image is exported and handed to a narrowly privileged publishing job. That job loads and pushes the same image to GitHub Container Registry, tagged with the full commit SHA:

- `ghcr.io/<lowercase-owner>/example-voting-app-vote:<full-github-sha>`
- `ghcr.io/<lowercase-owner>/example-voting-app-result:<full-github-sha>`
- `ghcr.io/<lowercase-owner>/example-voting-app-worker:<full-github-sha>`

The workflow uses `GITHUB_TOKEN` for GHCR authentication. Repository Actions settings must allow the token to write packages for push publishing to succeed. A passing GitHub Actions run remains the evidence that the build and scan gates have succeeded; this document does not claim a passing run before one has been executed.
