variable "s3_bucket_name" {
  description = "The S3 bucket where the RDS logs are saved to"
}

variable "lambda_function_name" {
  description = "The Lambda function name to be triggered by the created CloudWatch event rule"
}

variable "lambda_function_arn" {
  description = "The Lambda function ARN to be triggered by the created CloudWatch event rule"
}

variable "rds_instance_name" {
  description = "The RDS instance name to retrieve logs from"
}

variable "rate" {
  description = "The CloudWatch event rule rate, e.g. 30 minutes, 1 hour, etc."
}

variable "min_file_size" {
  description = "The minimum file size in bytes of the RDS logs to process"
}

variable "region" {
  description = "The AWS region, e.g. us-east-1"
}

variable "log_prefix" {
  description = "The prefix of the log files to filter"
}
