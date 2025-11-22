"""
Script to create the DynamoDB table for storing user plantings.

Run this script once to create the table:
    python scripts/create_dynamodb_table.py

Requirements:
    - AWS credentials configured (via environment variables, IAM role, or ~/.aws/credentials)
    - boto3 installed
    - Appropriate AWS permissions to create DynamoDB tables
"""

import boto3
import os
from botocore.exceptions import ClientError

# Configuration
TABLE_NAME = os.getenv('DYNAMODB_PLANTINGS_TABLE_NAME', 'user_plantings')
REGION = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')

def create_table():
    """Create the DynamoDB table for user plantings."""
    dynamodb = boto3.client('dynamodb', region_name=REGION)
    
    try:
        response = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {
                    'AttributeName': 'user_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'  # String
                }
            ],
            BillingMode='PAY_PER_REQUEST'  # On-demand pricing
        )
        
        print(f"Creating table {TABLE_NAME}...")
        print(f"Table ARN: {response['TableDescription']['TableArn']}")
        print("Waiting for table to be active...")
        
        # Wait for table to be created
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=TABLE_NAME)
        
        print(f"✓ Table {TABLE_NAME} created successfully!")
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table {TABLE_NAME} already exists.")
            return True
        else:
            print(f"Error creating table: {e}")
            return False

if __name__ == '__main__':
    create_table()

