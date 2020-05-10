output "cloudwatch_event_rule_name" {
  value = aws_cloudwatch_event_rule.rds_logs_to_s3.name
  description = "The CloudWatch event rule name"
}

output "cloudwatch_event_rule_arn" {
  value = aws_cloudwatch_event_rule.rds_logs_to_s3.arn
  description = "The CloudWatch event rule ARN"
}

output "cloudwatch_event_target_id" {
  value = aws_cloudwatch_event_target.rds_logs_to_s3.id
  description = "The CloudWatch event target ID"
}

output "cloudwatch_event_target_arn" {
  value = aws_cloudwatch_event_target.rds_logs_to_s3.arn
  description = "The CloudWatch event target ARN"
}

output "allow_cloudwatch_lambda_permission_id" {
  value = aws_lambda_permission.allow_cloudwatch.id
  description = "The CloudWatch 'invoke lambda' permission ID"
}
