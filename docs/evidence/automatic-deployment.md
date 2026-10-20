# Automatic deployment evidence

Verified on 20 October 2026. This records an executed course deployment, not
only a workflow configuration review.

## GitHub-to-cluster run

- Repository: `Ecstasywonder/example-voting-app`.
- Source commit: `926228b262f1c535e9eff65730f83259f52347a5`.
- [Workflow run 39486670544](https://github.com/Ecstasywonder/example-voting-app/actions/runs/39486670544), attempt 2: all eight jobs passed.
- Compose E2E, all three strict Trivy/build jobs, and all three publication jobs
  succeeded in attempt 1. The deployment retry reused their scanned images.
- Deployment job: `118852798183`.
- SSM command: `ce355357-59a3-4370-841e-ada768884cfc`.
- Private cluster: `i-0974f7712a1dc61ab`, `172.31.32.4`.
- Helm release `voting`, namespace `voting`, revision **5**, status `deployed`.
- The fixed node command completed its post-upgrade application E2E test.

| Image | Immutable digest |
| --- | --- |
| `ghcr.io/ecstasywonder/example-voting-app-vote` | `sha256:b88c2b77c105b90876097f21131279e61617cbc24a5578192c4e0f464bbf85d4` |
| `ghcr.io/ecstasywonder/example-voting-app-result` | `sha256:46deeae461d8b141a5308d5aeca72675ac6b824c946a74c6d737c603b8c82b73` |
| `ghcr.io/ecstasywonder/example-voting-app-worker` | `sha256:670b03a68e274e0207266d5d5b0145c20e8385df0917d368dc223ffdb84d58bf` |

The workflow supplies the full commit tag plus each digest to Helm. The digest,
not a mutable tag lookup, selects the deployed image.

An independent private-SSH check confirmed all five Deployments at `1/1` and
the three running container image IDs matching those digests. A second in-cluster
E2E run passed, including changing the same voter's choice without adding a vote.
Persistent identities were unchanged from the earlier rollback demonstration:

- `db-data`: `c65cf564-0966-4c27-8c07-af2c0f35542f`.
- `redis-data`: `d18a8eab-08e0-468c-8890-83cd5a56e039`.
- Database Secret UID (not its contents): `bdd44a9b-518c-4fcc-9282-24e89dd75cb9`.

The node retains generated evidence logs under
`/home/ubuntu/ts-academy-capstone/evidence/`, including
`automated-deployment-validation.txt` and
`deployment-boundary-validation.txt`.

## Failed attempt and correction

Attempt 1 reached deployment but failed before sending an SSM command:
`Not authorized to perform sts:AssumeRoleWithWebIdentity`.

CloudTrail showed the exact subject actually issued by GitHub:

```text
repo:Ecstasywonder@56361947/example-voting-app@1418042624:ref:refs/heads/main
```

The original trust policy expected a legacy name-only subject. The owner and
repository IDs matched GitHub's repository metadata. Terraform changed only
that exact subject; the audience remained `sts.amazonaws.com`, the provider
remained exact, and no wildcard or legacy-subject fallback was added.
[GitHub documents this immutable subject format](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
The retry authenticated and deployed successfully.

## Infrastructure and access checks

- Initial reviewed plan: six deployment-access additions, one in-place instance
  profile attachment, zero deletions or compute replacements, no ingress changes.
- The first apply stopped on a missing exact-document
  `ssm:DescribeDocumentPermission` read. After granting that read, the existing
  document's content was verified against the plan and its failed-create marker
  was cleared. No SSM document was deleted or recreated.
- Final trust correction plan: zero additions, one role trust update, zero
  deletions. Subsequent Terraform plan: **No changes**.
- Both temporary workstation write grants were removed. The workstation's only
  remaining inline policy was `TSAcademyTerraformMetadataRead`.
- SSM agent `3.3.4793.0` registered `Online` after the instance profile attachment.
- AWS Access Analyzer returned no findings for both permissions boundaries,
  the bootstrap grant, and the separate exact-role trust-update grant.
- EC2 validation passed shell syntax, Terraform formatting/validation, actionlint,
  all nine Python deployment tests, and the three-image digest handoff test.
- Namespace impersonation checks denied nodes, namespaces, roles, rolebindings,
  ServiceAccounts, and TokenRequest access. Expected namespace deployment and
  pod-exec operations were allowed.
- Restricted Pod Security `v1.36` denied a privileged Pod in a server-side dry run.
- Installed scripts were root-owned `0755`; the public server CA was
  `root:capstone-deployer` `0640`. No administrator kubeconfig was copied.

The deployment identity can manage namespace Secrets because Helm stores its
release state there. The legacy ServiceAccount-token Secret risk and currently
unprotected `main` are explicitly documented in
[the deployment boundary](../../deployment/README.md). These are residual course
demonstration risks, not production security claims.
