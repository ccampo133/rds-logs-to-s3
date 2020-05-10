# CloudWatch Terraform Module

This module is used to create scheduled CloudWatch Event Rules, and link them to the `rds_logs_to_s3` Lambda function as
triggers.

It should exclusively be used by the `rds_logs_to_s3` Terraform code, and is not intended to be used as a standalone 
module.

See [`variables.tf`](./variables.tf) and [`outputs.tf`](outputs.tf) for information on inputs and outputs respectively.
