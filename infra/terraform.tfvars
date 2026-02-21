# Example Terraform variables
# Copy to terraform.tfvars and edit

aws_region       = "us-east-1"
environment      = "demo"
instance_type    = "t3.micro"
key_name         = "codebuzz_kp"       # SSH key name (must exist in AWS)
# Allow SSH and app from anywhere (required for GitHub Actions to deploy / run pipeline)
allowed_cidr     = "0.0.0.0/0"
app_port         = 8501
s3_bucket_prefix = "survey-qa-data"

# Grant EC2 role access to this bucket (fixes "No CSV or ZIP" / IAM access). Use your bucket name.
ec2_additional_s3_bucket_arns = ["arn:aws:s3:::survey-qa-data-301625833185"]
