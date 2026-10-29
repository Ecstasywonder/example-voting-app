<!-- PORTFOLIO_STAR_V1 -->
# Voting Application — AWS/Kubernetes Delivery Capstone

**Portfolio case study — Situation · Task · Action · Result (STAR)**

### Situation
An upstream distributed voting sample required repeatable cloud provisioning and a controlled deployment path.

### Task
Build an end-to-end infrastructure and delivery workflow while keeping services and administrative interfaces private.

### Action
Added Terraform-based AWS/K3s infrastructure, Helm release configuration, Compose integration checks, GitHub Actions builds and Trivy scanning, immutable GHCR image references, and GitHub OIDC to AWS SSM deployment controls.

### Result
The README documents a successful automatic deployment on 20 October 2026 (workflow run 39486670544, attempt 2), with eight passing jobs and Helm revision 5. The app itself originates from Docker's example-voting-app; the portfolio contribution is the delivery platform and operational evidence.

**Review the evidence:** [Architecture](docs/architecture/capstone-1.md) · [CI](docs/ci.md) · [Deployment evidence](docs/evidence/automatic-deployment.md)

> **Scope:** Results describe what the repository documents; they are not blanket claims of production readiness. Original/upstream code is credited where applicable.

---

## Detailed project documentation

# TS Academy DevOps Capstone 1: Voting Application

This repository is a course implementation of Docker, Terraform, Kubernetes,
Helm, CI, image scanning, and controlled deployment for the
[Docker example voting application](https://github.com/dockersamples/example-voting-app).
The upstream project remains the reference for the application itself; this
repository documents and supplies the capstone-specific deployment work.

The voting system has five running components: the Python Vote web service,
Redis queue, .NET Worker, PostgreSQL, and Node.js Result web service. The
local Compose setup also includes an optional one-shot seed service for
development.

## Capstone layout

- [Architecture](docs/architecture/capstone-1.md) describes the component,
  network, identity, and delivery boundaries.
- [Terraform](terraform/README.md) provisions the lowest-cost course cluster:
  one Terraform-owned K3s node in the existing AWS default VPC.
- [Helm](docs/helm.md) documents the single chart, private service access, and
  rollback demonstration.
- [Continuous integration](docs/ci.md) documents Compose tests, immutable
  image builds, Trivy gates, GHCR publishing, and the configured deployment
  handoff.
- [Node deployment boundary](deployment/README.md) documents the fixed SSM
  command, namespace-scoped Kubernetes identity, archive validation, and
  rollback behavior.

## What is deployed

The Helm release is named `voting` in namespace `voting`. It uses the single
chart at `helm/voting-app` and its single `values.yaml`. Application images are
referenced by full commit tag and immutable digest. Redis and PostgreSQL use
K3s `local-path` persistent claims; a rollback changes workloads while retaining
these claims. Database credentials are created only on the K3s node in the
pre-existing `voting-db` Secret and are not committed.

All application Services are `ClusterIP`. There is no public HTTP, HTTPS,
NodePort, LoadBalancer, or Kubernetes API access. Reach either web
service through an authenticated SSH path and a Kubernetes port-forward from
the EC2 workstation, for example:

```bash
sudo /usr/local/bin/k3s kubectl -n voting port-forward service/vote 8080:8080
sudo /usr/local/bin/k3s kubectl -n voting port-forward service/result 8081:8080
```

Run those commands in separate terminals on the private K3s node (or use the private workstation
tunnel described in the Terraform guide); they are intentionally not commands
for a public endpoint.

## Delivery controls

GitHub-hosted runners execute the Compose end-to-end test and build and scan
the three custom images on every push and pull request. Pull requests do not
publish. A push to `main` in `Ecstasywonder/example-voting-app` can publish the
already-scanned image and its immutable digest to GHCR. The workflow is
configured to pass the three verified digests to a fixed SSM document using a
short-lived GitHub OIDC role; it has no SSH key, static AWS key, or Kubernetes
administrator configuration.

The current [Capstone CI workflow](https://github.com/Ecstasywonder/example-voting-app/actions/workflows/ci.yml)
is public. Workflow configuration and the security properties of this handoff
are documented in [docs/ci.md](docs/ci.md).

Automatic deployment was verified on 20 October 2026 in
[run 39486670544, attempt 2](https://github.com/Ecstasywonder/example-voting-app/actions/runs/39486670544).
All eight jobs passed, and the SSM deployment completed at Helm revision 5.
[Deployment evidence](docs/evidence/automatic-deployment.md) records the exact
commit, image digests, authentication correction, and access checks. The manual
rollback procedure remains in [docs/helm.md](docs/helm.md).

## Operating constraints

All manual downloads, installations, Terraform operations, Helm operations,
and validation run on the designated EC2 hosts. The operator's local machine is
used only for source review, edits, and controlled SSH access. Private keys,
AWS credentials, kubeconfigs, Terraform state, plans, and generated database
credentials must stay out of Git.

The course brief refers to starter configurations, but none were supplied with
the brief. This repository uses the equivalent project layout above: Compose
files and Dockerfiles at the application root, Terraform under `terraform/`,
a single chart under `helm/voting-app/`, GitHub Actions under `.github/`, and
host deployment controls under `deployment/`.

## Local development

For application-only development, the upstream-compatible Compose definition
is retained. Its browser ports are local development ports, not the production
cluster exposure model:

```bash
docker compose up --build
```

See the [upstream README](https://github.com/dockersamples/example-voting-app#readme)
for the original application behavior and language-specific development notes.
