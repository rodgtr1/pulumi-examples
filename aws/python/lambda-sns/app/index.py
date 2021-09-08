import json
import boto3
from botocore.exceptions import ClientError
import os

def lambda_handler(event, context):
    client = boto3.client('sns')
    
    try:
        response = client.publish(
            TopicArn=os.environ['topic_arn'],
            Message='Test from SNS',
            Subject='Hi Travis',
        )
    except ClientError as error:
        print(f"Error publishing message: {error}")
    else:
        return {
            "statusCode": 200,
            "body": json.dumps({
                "response": response,
            }),
        }