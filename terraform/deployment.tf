locals {
  deployment_tags = {
    ManagedBy = "Terraform"
    Project   = "TS Academy DevOps Capstone"
  }

  account_id                        = "896986966867"
  github_oidc_provider_arn          = "arn:aws:iam::896986966867:oidc-provider/token.actions.githubusercontent.com"
  github_deploy_boundary_arn        = "arn:aws:iam::896986966867:policy/TSAcademyCapstoneGitHubDeployBoundary"
  cluster_ssm_boundary_arn          = "arn:aws:iam::896986966867:policy/TSAcademyCapstoneNodeSSMBoundary"
  ssm_managed_instance_core_arn     = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  github_deploy_role_name           = "TSAcademyCapstoneGitHubDeploy"
  cluster_ssm_role_name             = "TSAcademyCapstoneClusterSSM"
  cluster_ssm_instance_profile_name = "TSAcademyCapstoneClusterSSM"
  deployment_document_name          = "TSAcademyCapstoneDeployVoting"
}

data "aws_iam_openid_connect_provider" "github" {
  arn = local.github_oidc_provider_arn
}

resource "aws_iam_role" "cluster_ssm" {
  name                 = local.cluster_ssm_role_name
  permissions_boundary = local.cluster_ssm_boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "EC2AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = merge(local.deployment_tags, {
    Name = local.cluster_ssm_role_name
  })
}

resource "aws_iam_role_policy_attachment" "cluster_ssm_core" {
  role       = aws_iam_role.cluster_ssm.name
  policy_arn = local.ssm_managed_instance_core_arn
}

resource "aws_iam_instance_profile" "cluster_ssm" {
  name = local.cluster_ssm_instance_profile_name
  role = aws_iam_role.cluster_ssm.name

  tags = merge(local.deployment_tags, {
    Name = local.cluster_ssm_instance_profile_name
  })
}

resource "aws_ssm_document" "deploy" {
  name            = local.deployment_document_name
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy immutable voting application images on the private K3s node"
    parameters = {
      commitSha = {
        type              = "String"
        description       = "Full Git commit SHA approved by the CI pipeline"
        allowedPattern    = "^[a-f0-9]{40}$"
        interpolationType = "ENV_VAR"
      }
      voteDigest = {
        type              = "String"
        description       = "Immutable vote image digest"
        allowedPattern    = "^sha256:[a-f0-9]{64}$"
        interpolationType = "ENV_VAR"
      }
      resultDigest = {
        type              = "String"
        description       = "Immutable result image digest"
        allowedPattern    = "^sha256:[a-f0-9]{64}$"
        interpolationType = "ENV_VAR"
      }
      workerDigest = {
        type              = "String"
        description       = "Immutable worker image digest"
        allowedPattern    = "^sha256:[a-f0-9]{64}$"
        interpolationType = "ENV_VAR"
      }
    }
    mainSteps = [{
      action = "aws:runShellScript"
      name   = "runDeployment"
      precondition = {
        StringEquals = ["platformType", "Linux"]
      }
      inputs = {
        timeoutSeconds = "600"
        runCommand = [
          "set -eu; exec /usr/local/lib/ts-capstone/run-deployment \"$SSM_commitSha\" \"$SSM_voteDigest\" \"$SSM_resultDigest\" \"$SSM_workerDigest\""
        ]
      }
    }]
  })

  tags = merge(local.deployment_tags, {
    Name = local.deployment_document_name
  })
}

resource "aws_iam_role" "github_deploy" {
  name                 = local.github_deploy_role_name
  permissions_boundary = local.github_deploy_boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "GitHubMainBranchDeploy"
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "repo:Ecstasywonder@56361947/example-voting-app@1418042624:ref:refs/heads/main"
        }
      }
    }]
  })

  tags = merge(local.deployment_tags, {
    Name = local.github_deploy_role_name
  })
}

resource "aws_iam_role_policy" "github_deploy" {
  name = "TSAcademyCapstoneGitHubDeploy"
  role = aws_iam_role.github_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SendOnlyApprovedDeploymentDocument"
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = aws_ssm_document.deploy.arn
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = "us-east-1"
          }
        }
      },
      {
        Sid      = "SendOnlyToCapstoneCluster"
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = aws_instance.cluster.arn
        Condition = {
          StringEquals = {
            "aws:RequestedRegion"     = "us-east-1"
            "ssm:resourceTag/Name"    = "ts-academy-k3s"
            "ssm:resourceTag/Project" = "TS Academy DevOps Capstone"
          }
        }
      },
      {
        Sid      = "ReadOwnCommandResult"
        Effect   = "Allow"
        Action   = "ssm:GetCommandInvocation"
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = "us-east-1"
          }
        }
      },
      {
        Sid      = "DiscoverManagedClusterMetadata"
        Effect   = "Allow"
        Action   = "ssm:DescribeInstanceInformation"
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = "us-east-1"
          }
        }
      }
    ]
  })
}
