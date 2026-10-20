output "cluster_instance_id" {
  description = "Terraform-owned EC2 instance ID. Use this exact target for the later approved destroy/recreate demonstration."
  value       = aws_instance.cluster.id
}

output "cluster_private_ip" {
  description = "Private K3s API endpoint reachable only from the existing workstation."
  value       = aws_instance.cluster.private_ip
}

output "cluster_public_ip" {
  description = "Public SSH endpoint restricted by the cluster security group."
  value       = aws_instance.cluster.public_ip
}

output "cluster_security_group_id" {
  description = "Terraform-owned security group ID."
  value       = aws_security_group.cluster.id
}
