data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  key_name               = var.key_name != "" ? var.key_name : null
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.app.name

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = <<-EOF
    #!/bin/bash
    set -e

    # Install dependencies
    dnf update -y
    dnf install -y python3.11 python3.11-pip git docker

    # Start Docker
    systemctl enable docker
    systemctl start docker

    # Add ec2-user to docker group (allows running docker without sudo)
    usermod -aG docker ec2-user

    # Create app directory
    mkdir -p /opt/survey-qa
    chown ec2-user:ec2-user /opt/survey-qa

    # Signal ready (for healthcheck)
    touch /opt/survey-qa/.instance-ready
  EOF

  tags = {
    Name = "survey-qa-${var.environment}"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"

  tags = {
    Name = "survey-qa-${var.environment}-eip"
  }
}

resource "aws_iam_role" "app" {
  name = "survey-qa-${var.environment}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "app_s3" {
  name = "survey-qa-s3-access"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      # Terraform-managed bucket: ListBucket on bucket, GetObject/PutObject on objects
      [
        {
          Effect   = "Allow"
          Action   = ["s3:ListBucket"]
          Resource = [aws_s3_bucket.data.arn]
        },
        {
          Effect   = "Allow"
          Action   = ["s3:GetObject", "s3:PutObject"]
          Resource = ["${aws_s3_bucket.data.arn}/*"]
        }
      ],
      flatten([
        for arn in var.ec2_additional_s3_bucket_arns : [
          {
            Effect   = "Allow"
            Action   = ["s3:ListBucket"]
            Resource = [arn]
          },
          {
            Effect   = "Allow"
            Action   = ["s3:GetObject", "s3:PutObject"]
            Resource = ["${arn}/*"]
          }
        ]
      ])
    )
  })
}

resource "aws_iam_role_policy" "app_ecr" {
  name = "survey-qa-ecr-access"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_instance_profile" "app" {
  name = "survey-qa-${var.environment}-profile"
  role = aws_iam_role.app.name
}
