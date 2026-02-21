# Example Terraform variables
# Copy to terraform.tfvars and edit

aws_region       = "us-east-1"
environment      = "demo"
instance_type    = "t3.micro"
key_name         = "pipeline_demo"       # SSH key name (must exist in AWS)
#allowed_ssh_cidr = "0.0.0.0/0"        # Restrict to your IP for security
app_port         = 8501
s3_bucket_prefix = "survey-qa-data"

# Grant EC2 role access to this bucket (fixes "No CSV or ZIP" / IAM access). Use your bucket name.
ec2_additional_s3_bucket_arns = ["arn:aws:s3:::survey-qa-data-301625833185"]
