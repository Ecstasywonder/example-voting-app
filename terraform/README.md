# Terraform: Single-Node K3s Cluster

This configuration provisions one **new**, Terraform-owned Ubuntu 24.04 amd64 EC2 instance in the existing default VPC. It uses K3s rather than EKS to meet the capstone requirement at the lowest reasonable cost, while leaving enough room for the later Robot Shop observability stack.

## Scope and safeguards

- Uses existing VPC `vpc-0dcd1badcb27a2470` and default subnet `subnet-0ddbedcfd2b8e3a06` in `us-east-1d`; it does not create or modify a VPC, subnet, route table, NAT gateway, or the existing workstation.
- Creates exactly one security group and one `t3a.xlarge` EC2 instance by default. The instance has 4 vCPU, 16 GiB RAM, a 60 GiB encrypted gp3 root volume, IMDSv2 required, and standard CPU credits.
- Opens SSH only to the operator's `/32` and the existing workstation private `/32`. Opens the K3s API (`6443`) only to the workstation private `/32`. No HTTP, HTTPS, NodePort, or public Kubernetes API rule is created.
- K3s is installed from a fixed release and verified SHA-256. Traefik and ServiceLB are disabled. The K3s admin kubeconfig and server token remain on the node and are never rendered by Terraform.
- Outbound Internet access is left open so the node can install K3s and pull container images. Inbound application access will use SSH plus `kubectl port-forward`.
- `deployment.tf` adds two bounded IAM roles, one SSM managed-policy attachment, one cluster instance profile, one GitHub inline policy, and one fixed SSM document. It reuses the account's GitHub OIDC provider and attaches the profile to the existing cluster without replacement or new ingress rules.

## Review and apply

Run all installations, downloads, and Terraform commands on the existing EC2
workstation (`ubuntu@52.71.135.52`), not on the local machine. Source editing and
review can remain in this workspace. Terraform uses the workstation's instance
role; do not copy local AWS credentials or private keys onto EC2.

The verified Terraform executable lives in the persistent location
`/home/ubuntu/.local/bin/terraform`. Add `/home/ubuntu/.local/bin` to `PATH` for the
session before running the commands below. The persistent working directory is
`/home/ubuntu/ts-academy-capstone/capstone-1/example-voting-app/terraform`.

Use Terraform `1.13.5` or later. Commit `.terraform.lock.hcl`; do not commit `.terraform`, state, plans, `terraform.tfvars`, or kubeconfigs.

```bash
cd terraform
terraform init
terraform fmt -check
terraform validate
terraform plan -out=plan.tfplan
chmod 600 plan.tfplan
terraform show -json plan.tfplan > plan.tfplan.json
chmod 600 plan.tfplan.json
```

Review the plan and cost estimate before applying; an initial create does not
have an instance ID yet. Applying creates billable resources. Apply requires
reviewed temporary IAM permissions; their expiry must be renewed deliberately
for each approved operation, and they must be removed afterward. The historical
`iam/apply-jit.json` covers the original compute-only creation, not the complete
deployment configuration. Do not reuse it unchanged. The permanent metadata-read
policy grants no resource write access.

## Deployment access bootstrap

An operator first creates the fixed permissions boundaries from
`iam/deployment-github-boundary.json` and
`iam/deployment-node-ssm-boundary.json`. They intentionally live outside the
Terraform execution role's control. The cluster role is capped to SSM agent
traffic and project-prefixed Parameter Store reads; GitHub can invoke only the
fixed deployment document against the cluster, not arbitrary shell documents.

For adding deployment access to the existing cluster, review
`iam/deployment-bootstrap-jit.json`, replace its expired timestamps with a short
UTC expiry, and temporarily attach it to the workstation role. The expected plan
is six additions, one in-place instance-profile change, and no deletions. Stop
if the plan replaces compute or changes ingress. Remove the temporary policy
immediately after applying the reviewed saved plan. Subsequent resource updates
or teardown need newly reviewed scoped permissions; this bootstrap policy is
not a standing administrator grant.

Install the reviewed node-side boundary from [deployment](../deployment/README.md)
before enabling the workflow. No local AWS keys, SSH key, permanent Kubernetes
token, or administrator kubeconfig is passed to GitHub or copied onto EC2.

To satisfy the PDF's later destroy/recreate demonstration, first obtain explicit
confirmation, use only this directory, and confirm the resulting
`cluster_instance_id` before running `terraform destroy`. The create-only IAM
policy does not permit termination or security-group deletion.

## Private cluster access after an approved apply

From the existing workstation, copy `/etc/rancher/k3s/k3s.yaml` over SSH using restrictive local permissions. Then create an SSH tunnel from the workstation to the cluster's private address and set the copied kubeconfig server to `https://127.0.0.1:6443`. The certificate includes `127.0.0.1` as a TLS SAN for that tunnel. Keep the copied kubeconfig outside this repository.
