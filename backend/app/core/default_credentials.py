DEFAULT_CREDENTIALS = {
    "POSTGRESQL": {
        "host": "localhost",
        "port": 5432,
        "database": "postgres",
        "username": "postgres",
        "password": "root",
    },
    "MYSQL": {
        "host": "localhost",
        "port": 3306,
        "database": "test_db",
        "username": "root",
        "password": "root",
    },
    "SNOWFLAKE": {
        "account": "your_account.snowflakecomputing.com",
        "warehouse": "COMPUTE_WH",
        "database": "SAMPLE_DB",
        "username": "admin",
        "password": "your_snowflake_password",
    },
    "AWS_S3": {
        "aws_access_key_id": "your_aws_key",
        "aws_secret_access_key": "your_aws_secret",
        "region_name": "us-east-1",
        "bucket_name": "dataease-storage-bucket",
    }
}