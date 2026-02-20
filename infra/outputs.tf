output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Public IP of the EC2 instance"
  value       = aws_eip.app.public_ip
}

output "app_url" {
  description = "URL to access the application"
  value       = "http://${aws_eip.app.public_ip}:${var.app_port}"
}

output "s3_bucket" {
  description = "S3 bucket for survey data"
  value       = aws_s3_bucket.data.bucket
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.data.arn
}

output "security_group_id" {
  description = "Security group ID"
  value       = aws_security_group.app.id
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = var.key_name != "" ? "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_eip.app.public_ip}" : "No SSH key configured"
}
