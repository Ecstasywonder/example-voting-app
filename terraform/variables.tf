variable "aws_region" {
  description = "AWS region containing the existing workstation and default VPC."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Name prefix for Terraform-owned cluster resources."
  type        = string
  default     = "ts-academy-k3s"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,40}$", var.cluster_name))
    error_message = "cluster_name must be 3-40 lowercase letters, numbers, or hyphens."
  }
}

variable "vpc_id" {
  description = "Existing default VPC. Terraform must not create or alter VPC networking."
  type        = string
  default     = "vpc-0dcd1badcb27a2470"
}

variable "subnet_id" {
  description = "Existing default subnet in us-east-1d, shared only as placement for the new node."
  type        = string
  default     = "subnet-0ddbedcfd2b8e3a06"
}

variable "ubuntu_ami_id" {
  description = "Resolved Canonical Ubuntu 24.04 amd64 AMI. Update deliberately after verifying architecture."
  type        = string
  default     = "ami-0fa5967347d08d2df"
}

variable "instance_type" {
  description = "x86_64 instance type. t3a.xlarge provides 4 vCPU and 16 GiB for K3s plus observability."
  type        = string
  default     = "t3a.xlarge"
}

variable "key_name" {
  description = "Existing EC2 key pair used to administer the new node."
  type        = string
  default     = "test key"
}

variable "operator_cidr" {
  description = "Operator public IPv4 /32 permitted to SSH to the dedicated cluster node."
  type        = string
  default     = "105.113.111.49/32"

  validation {
    condition     = can(cidrhost(var.operator_cidr, 0)) && can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/32$", var.operator_cidr))
    error_message = "operator_cidr must be one IPv4 /32 address."
  }
}

variable "workstation_private_cidr" {
  description = "Private /32 of the existing EC2 workstation, used for SSH and the private K3s API only."
  type        = string
  default     = "172.31.42.166/32"

  validation {
    condition     = can(cidrhost(var.workstation_private_cidr, 0)) && can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/32$", var.workstation_private_cidr))
    error_message = "workstation_private_cidr must be one IPv4 /32 address."
  }
}

variable "k3s_version" {
  description = "Exact verified K3s release; do not replace this with a moving channel."
  type        = string
  default     = "v1.36.5+k3s1"

  validation {
    condition     = can(regex("^v[0-9]+\\.[0-9]+\\.[0-9]+\\+k3s[0-9]+$", var.k3s_version))
    error_message = "k3s_version must be an exact release in the form vX.Y.Z+k3sN."
  }
}

variable "k3s_binary_sha256" {
  description = "SHA-256 for the amd64 K3s binary from the pinned GitHub release."
  type        = string
  default     = "d73847bcd3c5fccef0115b372e2f9a91f3032dc84bbf71518a4617565294d313"

  validation {
    condition     = can(regex("^[a-f0-9]{64}$", var.k3s_binary_sha256))
    error_message = "k3s_binary_sha256 must be a lowercase SHA-256 digest."
  }
}
