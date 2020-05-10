resource "aws_cloudwatch_event_rule" "rds_logs_to_s3" {
  name = "rds_logs_to_s3_${var.rds_instance_name}"
  description = "Triggers moving logs from RDS (${var.rds_instance_name}) to S3."
  schedule_expression = "rate(${var.rate})"
}

resource "aws_cloudwatch_event_target" "rds_logs_to_s3" {
  rule = aws_cloudwatch_event_rule.rds_logs_to_s3.name
  target_id = aws_cloudwatch_event_rule.rds_logs_to_s3.name
  arn = var.lambda_function_arn
  input = <<INPUT
{
  "s3_bucket_name": "${var.s3_bucket_name}",
  "rds_instance_name": "${var.rds_instance_name}",
  "aws_region": "${var.region}",
  "log_prefix": "${var.log_prefix}",
  "min_size": ${var.min_file_size}
}
INPUT
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id = "allow_execution_from_cloudwatch_${var.rds_instance_name}"
  action = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.rds_logs_to_s3.arn
}
