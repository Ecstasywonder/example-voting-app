data "aws_vpc" "default" {
  default = true
}

data "aws_subnet" "cluster" {
  id = var.subnet_id
}

data "aws_ami" "cluster" {
  most_recent = false
  owners      = ["099720109477"]

  filter {
    name   = "image-id"
    values = [var.ubuntu_ami_id]
  }
}

data "aws_ec2_instance_type" "cluster" {
  instance_type = var.instance_type
}

resource "aws_security_group" "cluster" {
  name_prefix = "${var.cluster_name}-"
  description = "Private management access for the Terraform-owned single-node K3s cluster"
  vpc_id      = var.vpc_id

  ingress {
    description = "SSH from the course operator"
    protocol    = "tcp"
    from_port   = 22
    to_port     = 22
    cidr_blocks = [var.operator_cidr]
  }

  ingress {
    description = "SSH via the existing EC2 workstation"
    protocol    = "tcp"
    from_port   = 22
    to_port     = 22
    cidr_blocks = [var.workstation_private_cidr]
  }

  ingress {
    description = "K3s API from the existing EC2 workstation"
    protocol    = "tcp"
    from_port   = 6443
    to_port     = 6443
    cidr_blocks = [var.workstation_private_cidr]
  }

  egress {
    description = "Bootstrap packages, image pulls, and outbound workload traffic"
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name      = "${var.cluster_name}-sg"
    ManagedBy = "Terraform"
    Project   = "TS Academy DevOps Capstone"
  }
}

resource "aws_instance" "cluster" {
  ami                         = var.ubuntu_ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.cluster.id]
  key_name                    = var.key_name
  iam_instance_profile        = aws_iam_instance_profile.cluster_ssm.name
  associate_public_ip_address = true
  user_data = templatefile("${path.module}/templates/k3s-bootstrap.sh.tftpl", {
    k3s_version       = var.k3s_version
    k3s_binary_sha256 = var.k3s_binary_sha256
    node_name         = var.cluster_name
  })
  user_data_replace_on_change = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  credit_specification {
    cpu_credits = "standard"
  }

  volume_tags = {
    Name      = "${var.cluster_name}-root"
    ManagedBy = "Terraform"
    Project   = "TS Academy DevOps Capstone"
  }

  root_block_device {
    encrypted             = true
    volume_type           = "gp3"
    volume_size           = 60
    delete_on_termination = true
  }

  lifecycle {
    precondition {
      condition     = var.vpc_id == data.aws_vpc.default.id
      error_message = "vpc_id must be the AWS default VPC required by the capstone."
    }

    precondition {
      condition     = data.aws_subnet.cluster.vpc_id == var.vpc_id
      error_message = "subnet_id must belong to the selected existing default VPC."
    }

    precondition {
      condition     = data.aws_subnet.cluster.default_for_az && data.aws_subnet.cluster.map_public_ip_on_launch
      error_message = "subnet_id must be a default subnet that assigns public IPs for controlled SSH access."
    }

    precondition {
      condition     = contains(data.aws_ec2_instance_type.cluster.supported_architectures, "x86_64")
      error_message = "This K3s bootstrap downloads the verified amd64 binary; select an x86_64 instance type."
    }

    precondition {
      condition     = data.aws_ami.cluster.architecture == "x86_64"
      error_message = "ubuntu_ami_id must resolve to Canonical's Ubuntu 24.04 x86_64 AMI."
    }
  }

  tags = {
    Name      = var.cluster_name
    ManagedBy = "Terraform"
    Project   = "TS Academy DevOps Capstone"
  }
}
