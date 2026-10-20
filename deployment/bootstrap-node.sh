#!/bin/bash
set -Eeuo pipefail

readonly SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
readonly K3S=/usr/local/bin/k3s
readonly HELM=/usr/local/bin/helm
readonly DEPLOY_USER=capstone-deployer
readonly DEPLOY_HOME=/var/lib/ts-capstone/deployments
readonly DEPLOY_LIB=/usr/local/lib/ts-capstone
readonly DEPLOY_ETC=/etc/ts-capstone

if [[ $(id -u) -ne 0 ]]; then
  echo "bootstrap-node.sh must run as root on the K3s node" >&2
  exit 77
fi

for required_file in rbac.yaml run-deployment deploy_voting.py write_kubeconfig.py; do
  if [[ ! -f $SCRIPT_DIR/$required_file || -L $SCRIPT_DIR/$required_file ]]; then
    echo "missing reviewed source file: $required_file" >&2
    exit 66
  fi
done
for required_binary in "$K3S" "$HELM" /usr/bin/python3 /usr/bin/flock /usr/bin/timeout /usr/sbin/runuser; do
  if [[ ! -x $required_binary ]]; then
    echo "required preinstalled binary is unavailable: $required_binary" >&2
    exit 69
  fi
done
if [[ ! -r /var/lib/rancher/k3s/server/tls/server-ca.crt ]]; then
  echo "K3s server CA is unavailable; run this bootstrap on the server node" >&2
  exit 69
fi

if ! "$K3S" kubectl get namespace voting >/dev/null; then
  echo "the voting namespace must already exist" >&2
  exit 69
fi
if [[ $("$K3S" kubectl --namespace voting get secret voting-db \
  --output 'go-template={{if and (index .data "admin-password") (index .data "app-password")}}ready{{end}}' 2>/dev/null) != ready ]]; then
  echo "voting/voting-db must already contain admin-password and app-password" >&2
  exit 69
fi

if ! getent passwd "$DEPLOY_USER" >/dev/null; then
  useradd --system --user-group --home-dir "$DEPLOY_HOME" \
    --shell /usr/sbin/nologin --comment "TS capstone namespace deployer" "$DEPLOY_USER"
fi
if [[ $(getent passwd "$DEPLOY_USER" | cut -d: -f7) != /usr/sbin/nologin ]]; then
  echo "existing $DEPLOY_USER account does not have the required nologin shell" >&2
  exit 78
fi
deploy_group=$(id -gn "$DEPLOY_USER")

install -d -o root -g root -m 0755 /usr/local/lib/ts-capstone
install -d -o root -g root -m 0755 "$DEPLOY_LIB/no-plugins"
install -d -o root -g "$deploy_group" -m 0750 "$DEPLOY_ETC"
install -d -o "$DEPLOY_USER" -g "$deploy_group" -m 0700 /var/lib/ts-capstone "$DEPLOY_HOME"
install -o root -g root -m 0755 "$SCRIPT_DIR/run-deployment" "$DEPLOY_LIB/run-deployment"
install -o root -g root -m 0755 "$SCRIPT_DIR/deploy_voting.py" "$DEPLOY_LIB/deploy-voting"
install -o root -g root -m 0755 "$SCRIPT_DIR/write_kubeconfig.py" "$DEPLOY_LIB/write_kubeconfig.py"
install -o root -g root -m 0644 "$SCRIPT_DIR/rbac.yaml" "$DEPLOY_ETC/rbac.yaml"
install -o root -g "$deploy_group" -m 0640 \
  /var/lib/rancher/k3s/server/tls/server-ca.crt "$DEPLOY_ETC/server-ca.crt"

"$K3S" kubectl label namespace voting --overwrite \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/enforce-version=v1.36 \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/audit-version=v1.36 \
  pod-security.kubernetes.io/warn=restricted \
  pod-security.kubernetes.io/warn-version=v1.36
"$K3S" kubectl apply --filename "$DEPLOY_ETC/rbac.yaml"

echo "installed private K3s deployment boundary"
echo "SSM must invoke: $DEPLOY_LIB/run-deployment COMMIT_SHA VOTE_DIGEST RESULT_DIGEST WORKER_DIGEST"
