# Continuous Integration

`.github/workflows/ci.yml` runs on every push and pull request using GitHub-hosted `ubuntu-24.04` runners. It does not use a self-hosted runner or require repository secrets.

The pipeline first starts the existing Compose end-to-end suite from `result/docker-compose.test.yml`. It uses a unique Compose project name, saves container logs as an artifact when a test fails, and always removes the test containers and volumes.

Each application image is then built for `linux/amd64` and scanned with Trivy. Any HIGH or CRITICAL operating-system or library vulnerability fails the workflow. The report for every image is uploaded as a short-lived workflow artifact, including when the scan fails. Reports are sanitized JSON: vulnerability package metadata is retained, while secret findings retain only rule metadata and line locations, never matched values or source snippets. No Trivy ignore file or ignored-unfixed setting is used.

Pull requests only test, build, and scan. They do not log in to a registry, receive `packages: write`, or push images. For a push, the scanned Docker image is exported and handed to a narrowly privileged publishing job. That job loads and pushes the same image to GitHub Container Registry, tagged with the full commit SHA:

- `ghcr.io/<lowercase-owner>/example-voting-app-vote:<full-github-sha>`
- `ghcr.io/<lowercase-owner>/example-voting-app-result:<full-github-sha>`
- `ghcr.io/<lowercase-owner>/example-voting-app-worker:<full-github-sha>`

The workflow uses `GITHUB_TOKEN` for GHCR authentication. Repository Actions settings must allow the token to write packages for push publishing to succeed. A passing GitHub Actions run remains the evidence that the build and scan gates have succeeded; this document does not claim a passing run before one has been executed.

For each qualifying push to `main` in `Ecstasywonder/example-voting-app`, the publishing job inspects the local image's `RepoDigests` after the registry push and publishes a one-day, per-image JSON artifact containing the image name, GHCR repository, full commit SHA, and immutable `repository@sha256` digest. Pushes to other branches and forks run the build, end-to-end, and scan gates but cannot publish packages. This handoff is deliberately separate from the image tarball: the deployment job accepts exactly the three expected manifest filenames and validates their complete schema, expected repository names, unique image names, commit SHA, and digest format before it can request a deployment.

## Automatic deployment

After all three images have passed the existing end-to-end, build, and vulnerability gates and have been published, a deployment job runs automatically only for a push to `refs/heads/main` in `Ecstasywonder/example-voting-app`. Pull requests, pushes to other branches, and repository forks cannot enter this job.

The deployment job has only `id-token: write`; it has no repository checkout, package permission, long-lived AWS key, Kubernetes configuration, or SSH key. It assumes `arn:aws:iam::896986966867:role/TSAcademyCapstoneGitHubDeploy` through GitHub OIDC for 15 minutes, limited to AWS account `896986966867` and `us-east-1`. The role's OIDC trust policy exactly matches this repository's immutable subject, `repo:Ecstasywonder@56361947/example-voting-app@1418042624:ref:refs/heads/main`, and audience `sts.amazonaws.com`. This repository uses GitHub's immutable owner/repository ID format; a legacy name-only subject does not authenticate it. See [GitHub's AWS OIDC guidance](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).

Using the resulting short-lived role session, the job locates exactly one online SSM-managed instance tagged `Name=ts-academy-k3s` and `Project=TS Academy DevOps Capstone`. It verifies the instance ID and requires SSM Agent `3.3.2746.0` or later, which supports Run Command parameter interpolation as environment variables. After validating each full `repository@sha256:...` manifest against its expected repository, it passes the SHA-256 component (for example, `sha256:...`) with the full commit SHA to only the custom SSM document `TSAcademyCapstoneDeployVoting` at its `$DEFAULT` version. The document is managed separately and must constrain its parameters with `interpolationType: ENV_VAR` and the corresponding validation patterns.

The workflow records the SSM command ID early in the run summary and polls the command invocation for up to about 12 minutes. It accepts success only when SSM reports `Success` with response code `0`; terminal failure statuses fail the job. It does not grant or use `ssm:CancelCommand`.
