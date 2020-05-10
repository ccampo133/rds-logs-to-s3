import argparse
import datetime
import hashlib
import hmac
from datetime import datetime
from urllib.parse import quote_plus

import boto3
import urllib3
from botocore.exceptions import ClientError


def copy_logs_from_rds_to_s3(rds_instance_name, s3_bucket_name, region, log_prefix="", min_size=0):
    """
    Download log files from an RDS instance, and upload them to an S3 bucket. Adopted from AWS's RDS support tool
    'move-rds-logs-to-s3'.

    See: https://github.com/awslabs/rds-support-tools/tree/master/database-logs/move-rds-logs-to-s3

    :param rds_instance_name: The RDS instance name to download log files from
    :param s3_bucket_name: The S3 bucket to upload log files to
    :param region: The region where the S3 bucket and RDS instance are located
    :param log_prefix: Filter log files with this prefix
    :param min_size: The minimum size of log files to download, in bytes
    """
    config_file_name = f"{rds_instance_name}/backup_config"

    # Initialize
    rds_client = boto3.client('rds', region_name=region)
    s3_client = boto3.client('s3', region_name=region)
    http = urllib3.PoolManager()

    last_written_this_run = 0
    last_written_time = 0
    backup_start_time = datetime.now()

    # Check if the S3 bucket exists and is accessible
    try:
        s3_client.head_bucket(Bucket=s3_bucket_name)
    except ClientError as e:
        error_code = int(e.response['ResponseMetadata']['HTTPStatusCode'])
        if error_code == 404:
            raise RuntimeError(f"Error: Bucket name {s3_bucket_name} not found")
        raise RuntimeError(f"Error: Unable to access bucket name, error: {e.response['Error']['Message']}")

    # Get the config file, if the config isn't present this is the first run
    try:
        s3_response = s3_client.get_object(Bucket=s3_bucket_name, Key=config_file_name)
        last_written_time = int(s3_response['Body'].read(s3_response['ContentLength']))
        print(f"Retrieving files with last written time after {str(last_written_time)} and min size {str(min_size)} B")
    except ClientError as e:
        error_code = int(e.response['ResponseMetadata']['HTTPStatusCode'])
        if error_code == 404:
            print("It appears this is the first log import, all files will be retrieved from RDS")
            min_size = 0  # We don't want to filter by file size on the first run
        else:
            raise RuntimeError(f"Error: Unable to access config file, error: {e.response['Error']['Message']}")

    # Copy the logs in batches to s3
    copied_file_count = 0
    log_marker = ""
    more_logs_remaining = True
    while more_logs_remaining:
        db_logs = rds_client.describe_db_log_files(
            DBInstanceIdentifier=rds_instance_name,
            FilenameContains=log_prefix,
            FileLastWritten=last_written_time,
            Marker=log_marker,
            FileSize=min_size
        )
        if 'Marker' in db_logs and db_logs['Marker'] != "":
            log_marker = db_logs['Marker']
        else:
            more_logs_remaining = False

        # Copy the logs in this batch
        for db_log in db_logs['DescribeDBLogFiles']:
            print(f"FileNumber: {copied_file_count + 1}")
            filename = db_log['LogFileName']
            size = int(db_log['Size'])
            print(
                f"Downloading file: {filename} found w/ LastWritten value of: {db_log['LastWritten']} ({size} bytes)")
            if int(db_log['LastWritten']) > last_written_this_run:
                last_written_this_run = int(db_log['LastWritten']) + 1

            # Download the log file
            try:
                log_file_data = get_log_file_via_rest(http, filename, rds_instance_name, region)
            except Exception as e:
                print(f"File '{filename}' download failed: {e}")
                continue

            compressed_size = len(log_file_data)
            difference = 100 * (compressed_size - size) // size
            print(f"Compressed log file size: {compressed_size} bytes ({difference}% difference)")

            # Upload the log file to S3
            object_name = f"{rds_instance_name}/backup_{backup_start_time.isoformat()}/{filename}.gz"
            try:
                s3_client.put_object(Bucket=s3_bucket_name, Key=object_name, Body=log_file_data)
                copied_file_count += 1
            except ClientError as e:
                err_msg = f"Error writing object to S3 bucket, S3 ClientError: {e.response['Error']['Message']}"
                raise RuntimeError(err_msg)
            print(f"Uploaded log file {object_name} to S3 bucket {s3_bucket_name}")

    print(f"Copied {copied_file_count} file(s) to S3")

    # Update the last written time in the config
    if last_written_this_run > 0:
        try:
            s3_client.put_object(
                Bucket=s3_bucket_name,
                Key=config_file_name,
                Body=str.encode(str(last_written_this_run))
            )
        except ClientError as e:
            print(f"Error writing the config to S3 bucket, S3 ClientError: {e.response['Error']['Message']}")
            return
        print(f"Wrote new Last Written file to {config_file_name} in Bucket {s3_bucket_name} with timestamp {last_written_this_run}")

    print("Log file export complete")


def get_log_file_via_rest(http, filename, db_instance_identifier, region):
    """
    AWS's web API is a bit esoteric and requires an arduous signing process. In general, the process can
    be broken down into the following four steps:
    1. Create a canonical request
    2. Use the canonical request and additional metadata to create a string for signing.
    3. Derive a signing key from your AWS secret access key. Then use the signing key, and the string
       from the previous step, to create a signature.
    4. Add the resulting signature to the HTTP request in a header or as a query string parameter.

    Ultimately, this entire process is is necessary because the RDS SDK is broken when it comes to
    downloading log file portions from RDS (ugh).

    See:
    https://docs.aws.amazon.com/general/latest/gr/signature-version-4.html
    https://github.com/aws/aws-cli/issues/2268
    https://github.com/aws/aws-cli/issues/3079
    https://github.com/aws/aws-sdk-net/issues/921

    :param http: A urllib3 http client
    :param filename: The filename of the log file to download
    :param db_instance_identifier: The DB instance to download log files from
    :param region: The AWS region where the DB instance is located
    :return: The log file data, gzip encoded
    """

    method = 'GET'
    service = 'rds'
    host = f"rds.{region}.amazonaws.com"
    endpoint = f"https://{host}"

    # Credentials are intended to be implicitly provided and likely come from env vars or IAM roles
    credentials = boto3.Session().get_credentials()
    access_key = credentials.access_key
    secret_key = credentials.secret_key
    session_token = credentials.token
    if access_key is None or secret_key is None:
        raise RuntimeError('No access key is available.')

    # Create a date for headers and the credential string
    t = datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')  # Format date as YYYYMMDD'T'HHMMSS'Z'
    datestamp = t.strftime('%Y%m%d')  # Date w/o time, used in credential scope
    canonical_uri = f"/v13/downloadCompleteLogFile/{db_instance_identifier}/{filename}"

    # Create the canonical headers and signed headers. Header names and value must be trimmed
    # and lowercase, and sorted in ASCII order. Note trailing \n in canonical_headers. The
    # 'signed_headers' variable is the list of headers that are being included as part of the
    # signing process. For requests that use query strings, only 'host' is included in the
    # signed headers.
    canonical_headers = f"host:{host}\n"
    signed_headers = 'host'

    # Algorithm must match the hashing algorithm used, in this case SHA-256 (recommended)
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"

    # Build the canonical query string with the elements gathered above
    canonical_querystring = build_canonical_query_string(
        access_key,
        credential_scope,
        amz_date,
        signed_headers,
        session_token
    )

    # Create payload hash. For GET requests, the payload is an empty string ("").
    payload_hash = hashlib.sha256(''.encode("utf-8")).hexdigest()

    # Combine elements to create create the canonical API request
    canonical_request = \
        f"{method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    # Hash the request so it can be signed
    hashed_request = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
    string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashed_request}"

    # Create the signing key
    signing_key = get_signature_key(secret_key, datestamp, region, service)

    # Sign the hashed request (string_to_sign) using the signing key
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    # Add signing information to the request. The auth information can be either in the query
    # string value or in a header named Authorization. Here we put everything into the query
    # string.
    signed_querystring = f"{canonical_querystring}&X-Amz-Signature={signature}"

    # Send the API request. The 'host' header must exist as a header in the request. In this case,
    # it's is added automatically by the Python urllib3 lib.
    request_url = f"{endpoint}{canonical_uri}?{signed_querystring}"
    print(f"Request URL: {request_url}")

    # Setting the encoding to gzip has potential to save ~90% on file size
    response = http.request(method, request_url, decode_content=False, headers={"Accept-Encoding": "gzip"})
    print(f"Response code: {response.status}")

    if response.status > 200:
        raise RuntimeError(f"Could not download log file due to HTTP error status {response.status}")

    return response.data


def get_signature_key(key, date, region_name, service_name):
    """
    AWS key derivation functions.

    See: http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python

    :param key: The signing key
    :param date: The current date w/o time, YYYYMMDD
    :param region_name: The AWS region
    :param service_name: The AWS service name, e.g. RDS, S3, etc.
    :return: The signing key
    """

    def sign(k, msg): return hmac.new(k, msg.encode('utf-8'), hashlib.sha256).digest()

    key_date = sign(('AWS4' + key).encode('utf-8'), date)
    key_region = sign(key_date, region_name)
    key_service = sign(key_region, service_name)
    key_signing = sign(key_service, 'aws4_request')
    return key_signing


def build_canonical_query_string(access_key, credential_scope, amz_date, signed_headers, session_token=None):
    """
    Create the canonical query string. In this example, request parameters are in the query string. Query string values
    must be URL-encoded (space=%20). The parameters must be sorted by name.

    See: https://docs.aws.amazon.com/general/latest/gr/signature-version-4.html

    :param access_key: The AWS access key
    :param credential_scope: The AWS credential scope
    :param amz_date: The current date, in AWS's specific date format YYYYMMDD'T'HHMMSS'Z'
    :param signed_headers: The headers top be signed in the request
    :param session_token: The AWS session token, if it exists (default: None)
    :return: The canonical query string, as defined in the AWS documentation
    """
    credentials = quote_plus(f"{access_key}/{credential_scope}")
    canonical_querystring = 'X-Amz-Algorithm=AWS4-HMAC-SHA256' + \
                            f'&X-Amz-Credential={credentials}' \
                            f'&X-Amz-Date={amz_date}' + \
                            '&X-Amz-Expires=30' + \
                            f'&X-Amz-SignedHeaders={signed_headers}'
    if session_token is not None:
        canonical_querystring += f'&X-Amz-Security-Token={quote_plus(session_token)}'
    return canonical_querystring


def parse_args():
    parser = argparse.ArgumentParser(description='Move logs from RDS to S3.')
    parser.add_argument('--rds-instance-name', action='store', required=True, help='The RDS instance name')
    parser.add_argument('--s3-bucket-name', action='store', required=True, help='The S3 bucket name')
    parser.add_argument('--aws-region', action='store', required=True, help='The AWS region')
    parser.add_argument('--log-prefix', action='store', required=False,
                        help='Filter logs with this prefix (default: empty string)', default="")
    parser.add_argument('--min-size', action='store', required=False, type=int,
                        help='Filters logs less than the specified size in bytes (default: 0)', default=0)
    return parser.parse_args()


def lambda_handler(event, context):
    """
    Invoked by AWS Lambda. Args are expected to be passed as in the trigger event.

    See: https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html

    :param event: The Lambda event data. Assumed to be a 'dict' with the following keys:
                  * rds_instance_name: The RDS instance name to download log files from
                  * s3_bucket_name: The S3 bucket to upload log files to
                  * region: The region where the S3 bucket and RDS instance are located
                  * log_prefix: Filter log files with this prefix
                  * min_size: The minimum size of log files to download, in bytes
    :param context: The context of the Lambda invocation. See:
                    https://docs.aws.amazon.com/lambda/latest/dg/python-context.html
    """
    print("Invoked by Lambda event:", event)
    print("Request ID:", context.aws_request_id)
    print("Log stream name:", context.log_stream_name)
    print("Log group name:", context.log_group_name)
    print("Memory limit (MB):", context.memory_limit_in_mb)

    copy_logs_from_rds_to_s3(
        event['rds_instance_name'],
        event['s3_bucket_name'],
        event['aws_region'],
        event['log_prefix'],
        event['min_size']
    )


# Run from the command line
if __name__ == '__main__':
    args = parse_args()
    copy_logs_from_rds_to_s3(
        args.rds_instance_name,
        args.s3_bucket_name,
        args.aws_region,
        args.log_prefix,
        args.min_size
    )
