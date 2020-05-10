# rds-logs-to-s3

![Build master](https://github.com/ccampo133/rds-logs-to-s3/workflows/Build%20master/badge.svg)

Move RDS logs to S3. Adopted from [AWS's tool of a similar nature](https://github.com/awslabs/rds-support-tools/tree/master/database-logs/move-rds_logs_to_s3).

## Background

From AWS's own documentation:

> RDS allows you to view, download and watch the db log files through the RDS console. However, there is a retention 
> period for the log files and when the retention is reached, the logs are purged. There are situations where one might 
> want to archive the logs, so that they can access it in the future for compliance. In order to achieve that we can 
> move the RDS logs to S3 and keep it permanently in or you can download it to your local from S3. You can use this 
> script to incrementally move the log files to S3. 
>
> For example: 
>
> When you execute the script for the first time, all the logs will be moved to a new folder in S3 with the folder name
> being the instance name. And a sub-folder named "backup-<timestamp>" will contain the log files. When you execute the 
> script for the next time, then the log files since the last timestamp the script was executed will be copied to a new 
> folder named "backup-<new timestamp>". So you will have incremental backup.

In general, you should run this script in a shorter time period than when your logs are purged on the RDS instance. For
example, if you have audit logs configured to store in 100 MB files and rotate after 10 files, and you fill up a file
every 5 minutes, you should run this script at least every 50 minutes to ensure that you do not miss any data.

### Why not just use CloudWatch?

For MariaDB, MySQL, Oracle, PostgreSQL, and MS SQL Server, AWS allows you to automatically publish database log files to
[CloudWatch Logs](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_LogAccess.html). However, CloudWatch Logs
is not free. In fact, it can be quite expensive. For a moderately sized production database publishing ~2 TB of log
files per month, the CloudWatch costs will likely exceed $1000 in data transfer alone. 

Instead, you can run this script as an AWS Lambda function (see below) multiple times per hour, and still likely be in 
the free-tier so far as costs go.

If you have a low volume of data, I still recommend using CloudWatch just for simplicity's sake, however if you're
looking for a cost saving option here, keep reading.

## Usage

You can execute `rds_logs_to_s3` from either the command line or as an AWS Lambda function. Both approaches are detailed
below.

### Command Line

```
usage: rds_logs_to_s3.py [-h] --rds-instance-name RDS_INSTANCE_NAME
                         --s3-bucket-name S3_BUCKET_NAME --aws-region
                         AWS_REGION [--log-prefix LOG_PREFIX]
                         [--min-size MIN_SIZE]

Move logs from RDS to S3.

optional arguments:
  -h, --help            show this help message and exit
  --rds-instance-name RDS_INSTANCE_NAME
                        The RDS instance name
  --s3-bucket-name S3_BUCKET_NAME
                        The S3 bucket name
  --aws-region AWS_REGION
                        The AWS region
  --log-prefix LOG_PREFIX
                        Filter logs with this prefix (default: empty string)
  --min-size MIN_SIZE   Filters logs less than the specified size in bytes
                        (default: 0)
```

For example, to move `audit` logs from an RDS instance named `dev`, to an S3 bucket named `rds-audit-logs-dev`,
within the `us-east-1` region, with a max file size of 10 MB, you would do the following:

```
$ python3 rds_logs_to_s3.py \
  --rds-instance-name dev \
  --s3-bucket-name rds-audit-logs-dev \
  --aws-region us-east-1 \
  --log-prefix audit \
  --min-size 10000000
```

When the script finishes running, the logs will stored in S3 (gzip compressed).

### AWS Lambda

When executing as an AWS Lambda function, `rds_logs_to_s3` expects all arguments to be passed as an event of the 
following JSON format:

```json
{
  "s3_bucket_name": "string",
  "rds_instance_name": "string",
  "aws_region": "string",
  "log_prefix": "string",
  "min_size": 10000000
}
```

Within Lambda itself, the handler method should be configured as `rds_logs_to_s3.lambda_handler`.

Assuming the function is created and exists in Lambda already (for example, called `rds_logs_to_s3`), deployment is 
simple using the command line:

```
$ zip rds_logs_to_s3.zip rds_logs_to_s3.py
$ aws lambda update-function-code --function-name rds_logs_to_s3 --zip-file fileb://rds_logs_to_s3.zip
```

Pay attention to the size of your log files. The Lambda will essentially download them into memory before uploading them
to S3, so you will need to tweak the Lambda timeout and memory size accordingly. The logs will be downloaded in gzip 
format and will likely be compressed ~90%, so memory usage should not be high, but this is something that will vary and
must be tweaked on a per-use-case basis. 

Personally, I have found the lambda to consume less than 256 MB, even when downloading 200 MB individual log file (due 
to substantial compression).

This project includes functional [Terraform](https://www.terraform.io/) code to deploy this as a Lambda function to an 
AWS environment. See [`terraform`](terraform) for more details. 

## Development

Requires: Python 3.7

Create a [virtualenv](https://docs.python.org/3/library/venv.html):
                    
    $ python3 -m venv venv  
    # ...or just 'python', assuming that points to a >=Python 3.7 installation

Then activate it:

    $ source venv/bin/activate

Next, install the requirements:
    
    $ pip install -r requirements.txt

### CI/CD

This project is build with GitHub Actions. See [`.github/workflows`](.github/workflows) for specifics. 
