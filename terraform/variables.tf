# Required
variable "lambda_role_arn" {
  description = "The IAM role used by the Lambda function"
}

variable "rds_instance_name" {
  description = "The RDS instance name to retrieve logs from"
}

variable "s3_bucket_name" {
  description = "The name of the S3 bucket which log files will be saved to"
}

# Optional
variable "profile" {
  default = "default"
  description = "The AWS credentials profile"
}

variable "region" {
  default = "us-east-1"
  description = "The AWS region"
}

variable "rate" {
  default = "30 minutes"
  description = "The CloudWatch event rule rate, e.g. 30 minutes, 1 hour, etc."
}

variable "min_file_size" {
  default = "0"
  description = "The minimum file size in bytes of the RDS logs to process"
}

variable "lifecycle_rule_enabled" {
  default = true
  type = bool
  description = "If true, enables a lifecycle rule on the S3 bucket to delete old files (see: expiration_days)"
}

variable "expiration_days" {
  default = 7
  type = number
  description = "If 'lifecycle_policy_enabled' is true, set this to determine the number of expiration days"
}

variable "log_prefix" {
  default = ""
  description = "Filter log files with this prefix"
}

variable "memory_size" {
  default = 256
  type = number
  description = "The runtime memory of the Lambda, in MB. You'll likely need to tweak this depending on your log volume"
}

variable "timeout" {
  default = 300
  type = number
  description = "The Lambda timeout, in seconds. You'll likely need to tweak this depending on your log volume"
}
