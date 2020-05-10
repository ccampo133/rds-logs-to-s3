output "lambda_function_arn" {
  value = aws_lambda_function.rds_logs_to_s3.arn
  description = "The AWS Lambda function ARN"
}
