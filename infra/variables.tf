variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g. demo, dev, prod)"
  type        = string
  default     = "demo"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "SSH key pair name (must exist in AWS)"
  type        = string
  default     = ""
}

variable "app_port" {
  description = "Port the Streamlit app runs on"
  type        = number
  default     = 8501
}

variable "allowed_cidr" {
  description = "CIDR block allowed to access EC2 (SSH, app, HTTPS). Set to your IP/32 for security."
  type        = string
  default     = "173.66.55.228/32"
}

variable "allowed_ssh_cidr" {
  description = "Deprecated: Use allowed_cidr instead"
  type        = string
  default     = "173.66.55.228/32"
}

variable "s3_bucket_prefix" {
  description = "Prefix for S3 bucket name (account ID appended)"
  type        = string
  default     = "survey-qa-data"
}
