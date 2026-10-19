# Helm deployment and rollback

`helm/voting-app` is the project's one chart and has one `values.yaml`. The application resolves `redis` and `db` directly, so install only one release per namespace. All Services are `ClusterIP`; the chart creates no public listener. NetworkPolicies deny release-wide ingress by default, then permit namespace-local HTTP clients and only the required vote/worker-to-Redis and result/worker-to-PostgreSQL paths.

The image references are immutable `tag@sha256:digest` values. The chart never creates or holds database passwords. PostgreSQL receives `admin-password` only for database initialization. Result and Worker receive the separate `app-password` for the non-superuser `voting_app` role; the initialization script grants that role only database connection plus `USAGE` and `CREATE` on `public` so it can create the application's table. Run these commands on the K3s node; Helm and the K3s kubeconfig are intentionally installed there, not on the workstation. The Secret bootstrap is idempotent: it generates both random values only when the Secret does not yet exist, uses mode 0600 temporary files, prints no value, and does not pass passwords as command arguments. Never rotate either Secret key without first changing the corresponding PostgreSQL role password inside the retained database PVC.

```bash
sudo k3s kubectl create namespace voting --dry-run=client -o yaml | sudo k3s kubectl apply -f -
if ! sudo k3s kubectl -n voting get secret voting-db >/dev/null 2>&1; then
  umask 077
  VOTING_ADMIN_FILE=$(mktemp)
  VOTING_APP_FILE=$(mktemp)
  trap 'rm -f "$VOTING_ADMIN_FILE" "$VOTING_APP_FILE"' EXIT
  openssl rand -base64 36 | tr -d '\n' >"$VOTING_ADMIN_FILE"
  openssl rand -base64 36 | tr -d '\n' >"$VOTING_APP_FILE"
  sudo k3s kubectl -n voting create secret generic voting-db \
    --from-file=admin-password="$VOTING_ADMIN_FILE" \
    --from-file=app-password="$VOTING_APP_FILE"
  rm -f "$VOTING_ADMIN_FILE" "$VOTING_APP_FILE"
  trap - EXIT
fi
```

Render, then install on the K3s node:

```bash
sudo /usr/local/bin/helm lint helm/voting-app
sudo /usr/local/bin/helm template voting helm/voting-app --namespace voting > /tmp/voting-rendered.yaml
sudo /usr/local/bin/helm upgrade --install voting helm/voting-app --namespace voting --create-namespace --wait --timeout 5m --kubeconfig /etc/rancher/k3s/k3s.yaml
sudo k3s kubectl -n voting get deploy,pods,svc,pvc,networkpolicy
```

K3s's `local-path` class is the expected storage choice. PostgreSQL and Redis are `Recreate` Deployments with persistent claims. A Helm rollback changes workloads but retains both claims and their data. Do not use `helm uninstall` during this exercise.

To prove rollback, record the healthy revision and PVC UIDs, then introduce a nonexistent Result digest with `--set`, not a second values file. `--atomic` is deliberately omitted so the failed revision is observable:

```bash
GOOD_REVISION=$(sudo /usr/local/bin/helm -n voting history voting -o json --kubeconfig /etc/rancher/k3s/k3s.yaml | jq -r '.[-1].revision')
sudo k3s kubectl -n voting get pvc db-data redis-data -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.metadata.uid}{"\n"}{end}'
sudo /usr/local/bin/helm upgrade voting helm/voting-app --namespace voting --wait --timeout 90s --kubeconfig /etc/rancher/k3s/k3s.yaml \
  --set result.image.digest=sha256:$(printf '0%.0s' {1..64})
sudo /usr/local/bin/helm -n voting status voting --kubeconfig /etc/rancher/k3s/k3s.yaml
sudo /usr/local/bin/helm rollback voting "$GOOD_REVISION" --namespace voting --wait --timeout 5m --kubeconfig /etc/rancher/k3s/k3s.yaml
sudo k3s kubectl -n voting get deploy,pods,svc,pvc,networkpolicy
sudo k3s kubectl -n voting get pvc db-data redis-data -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.metadata.uid}{"\n"}{end}'
```

After rollback, verify the PVC UIDs are unchanged and all five Deployments are available. The project end-to-end test supplies application-level verification. Result and Worker use the chart-initialized, non-superuser `voting_app` role rather than the PostgreSQL administrator role.
