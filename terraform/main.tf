terraform {
  required_version = ">= 0.12.6"

  backend "s3" {
    key    = "rds_logs_to_s3.tfstate"
  }
}

provider "aws" {
  version = "~> 2.60"

  profile = var.profile
  region = var.region
}

resource "aws_s3_bucket" "rds_logs" {
  bucket = var.s3_bucket_name

  # Logs are kept for
  lifecycle_rule {
    id      = "delete_old_files"
    enabled = var.lifecycle_rule_enabled

    expiration {
      days = var.expiration_days
    }

    noncurrent_version_expiration {
      days = var.expiration_days
    }
  }
}

resource "aws_lambda_function" "rds_logs_to_s3" {
  function_name = "rds_logs_to_s3"
  handler = "rds_logs_to_s3.lambda_handler"
  role = var.lambda_role_arn
  runtime = "python3.7"
  memory_size = var.memory_size
  timeout = var.timeout

  # Terraform needs a file to bootstrap the Lambda function, so we just use a dummy.
  filename = "dummy.zip"
}

# Create the CloudWatch event triggers for the Lambda function. You can create multiple of these if you want different
# cron triggers for the Lambda.
module "cloudwatch_event_trigger_audit_logs" {
  source = "./modules/cloudwatch"
  region = var.region
  lambda_function_arn = aws_lambda_function.rds_logs_to_s3.arn
  lambda_function_name = aws_lambda_function.rds_logs_to_s3.function_name
  rate = var.rate
  rds_instance_name = var.rds_instance_name
  s3_bucket_name = aws_s3_bucket.rds_logs.bucket
  min_file_size = var.min_file_size
  log_prefix = var.log_prefix
}
