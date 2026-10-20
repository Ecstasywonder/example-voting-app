# Private K3s deployment boundary

This directory is the reviewed host-side deployment boundary for the private K3s node. The GitHub workflow does not receive SSH material, AWS access keys, the K3s administrator kubeconfig, or a permanent Kubernetes credential. Its OIDC-authorized SSM command may call only the root-owned interface below; the SSM document and IAM policy are managed separately.

```text
/usr/local/lib/ts-capstone/run-deployment COMMIT_SHA VOTE_DIGEST RESULT_DIGEST WORKER_DIGEST
```

`COMMIT_SHA` is exactly 40 lowercase hexadecimal characters. Each digest is `sha256:` plus 64 lowercase hexadecimal characters. Do not construct an inline shell command from workflow inputs. Map the four SSM document parameters to four positional arguments of this fixed executable.

## One-time cluster preparation

Run preparation directly on the existing Ubuntu K3s server through SSH. Do not install or download software from these scripts. Before bootstrap, create the namespace and database Secret with the node's administrator kubeconfig. Values are generated on the node, are never printed, and are never stored in Git:

```bash
sudo /usr/local/bin/k3s kubectl create namespace voting
sudo sh -eu -c '
  umask 077
  work=$(mktemp -d)
  trap "rm -rf -- \"$work\"" EXIT HUP INT TERM
  openssl rand -base64 36 | tr -d "\n" >"$work/admin-password"
  openssl rand -base64 36 | tr -d "\n" >"$work/app-password"
  /usr/local/bin/k3s kubectl --namespace voting create secret generic voting-db \
    --from-file=admin-password="$work/admin-password" \
    --from-file=app-password="$work/app-password"
'
```

Review the five deployment source files locally. Upload only those files to a new staging directory on the node, then run the uploaded bootstrap as root over SSH. The private SSH key remains on the operator workstation; never copy it or local AWS credentials to the node.

```bash
scp -i "$CAPSTONE_SSH_KEY" \
  deployment/bootstrap-node.sh deployment/rbac.yaml deployment/run-deployment \
  deployment/deploy_voting.py deployment/write_kubeconfig.py \
  "ubuntu@$CAPSTONE_NODE:/tmp/ts-capstone-bootstrap/"
ssh -i "$CAPSTONE_SSH_KEY" "ubuntu@$CAPSTONE_NODE" \
  'sudo bash /tmp/ts-capstone-bootstrap/bootstrap-node.sh'
```

The bootstrap requires preinstalled `/usr/local/bin/k3s`, `/usr/local/bin/helm`, and Python. It refuses to create the namespace or Secret. It creates a no-login `capstone-deployer` system account, installs fixed root-owned scripts, copies only the public K3s server CA, applies the namespace Role, and pins Pod Security Admission enforce/audit/warn labels to `restricted:v1.36`. Re-run the same reviewed bootstrap after changing any file in this directory. Remove the staging directory after review and installation if operational policy requires it.

## Runtime and rollback

The root wrapper validates all four arguments before state changes and holds a root-only `flock` before minting credentials. An outer 570-second watchdog covers lock acquisition, credential creation, archive retrieval, Helm, E2E, rollback, and cleanup, leaving time before SSM's 600-second command limit to terminate child processes. It requests a 15-minute ServiceAccount token, writes a root-owned and group-readable kubeconfig in a new per-run `/run` directory, changes to the deployer's private home before dropping privilege, runs the fixed deployer as the no-login user with a clean environment, and deletes the kubeconfig and token directory on exit. The administrator kubeconfig is never copied or exposed.

After taking the lock, the deployer fails closed unless GitHub reports the requested full SHA as the current `main`. It downloads that commit from the fixed public GitHub archive host into a new private temporary directory and checks `main` again immediately before the mutating Helm upgrade. Its bounded parser writes only `helm/voting-app` and `result/tests/tests.py`; archive paths, member types, duplicates, counts, and sizes are validated. Downloaded source is never executed on the host. Helm receives the chart, and the standard-library E2E source is piped to `python -` inside the Vote pod.

Helm uses the chart's single `values.yaml` and overrides only the three commit tags and verified image digests. `upgrade --install` is limited to three minutes and uses Helm 4 `--rollback-on-failure`; post-upgrade E2E is limited to 90 seconds. If the E2E test fails, the deployer attempts a two-minute rollback to the previously deployed revision and still reports failure. A first install has no prior revision: an E2E failure is reported without automatic uninstall or PVC deletion so state remains available for investigation.

The Role is confined to `voting`. It cannot manage namespaces, nodes, persistent volumes, RBAC objects, ServiceAccounts, or the TokenRequest API. Helm stores release state in Secrets, so this trusted-main deployer can read and mutate all Secrets in `voting`, including `voting-db`; keep unrelated workloads and credentials out of that namespace. Secret creation also permits the legacy ServiceAccount-token Secret mechanism, despite the TokenRequest restriction. A compromised trusted chart can therefore steal namespace credentials or persist namespace access. It can also manage namespace NetworkPolicies because those policies are part of the Helm release. The trust boundary includes repository writers, image digest production, the fixed SSM document, and this installed host code.

The repository's `main` branch was not protected when checked on 20 October 2026. This is a course demonstration, not a production security boundary. Before production use, enable branch protection with required CI checks and reviewed changes, and add administrator-owned admission controls denying legacy ServiceAccount-token Secrets from this deployment identity. Restricted Pod Security is enforced now; it does not prohibit that Secret mechanism.

## Focused validation

All installation, download, Helm, Kubernetes, and E2E commands must run on the EC2 node. On the node, archive parser tests can be run from the reviewed staging copy before bootstrap:

```bash
python3 -m unittest -v deployment/tests/test_archive_validation.py
```

After bootstrap, validate the negative authorization boundary with a freshly minted short-lived token or impersonation from the administrator context. Expected allowed resources are the Role rules in `rbac.yaml`; these examples must print `no`:

```bash
sudo /usr/local/bin/k3s kubectl auth can-i create clusterrole \
  --as=system:serviceaccount:voting:capstone-deployer
sudo /usr/local/bin/k3s kubectl auth can-i create namespace \
  --as=system:serviceaccount:voting:capstone-deployer
sudo /usr/local/bin/k3s kubectl auth can-i create serviceaccount --namespace voting \
  --as=system:serviceaccount:voting:capstone-deployer
sudo /usr/local/bin/k3s kubectl auth can-i get nodes \
  --as=system:serviceaccount:voting:capstone-deployer
```

Deployment logs intentionally include the source commit, archive SHA-256, Helm output, and final Result digest. They must never contain the ServiceAccount token, kubeconfig, database passwords, SSH key, or AWS credentials.
