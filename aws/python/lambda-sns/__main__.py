import pulumi
import pulumi_aws as aws
import json

# Create the role for the Lambda to assume
def create_lambda_role():
    # Create the role
    lambda_role = aws.iam.Role("lambdaSNSRole", 
        assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Principal": {
                        "Service": "lambda.amazonaws.com",
                    },
                    "Effect": "Allow",
                    "Sid": "",
                }
            ]
        }))

    # Create policy to publish to SNS
    sns_policy = aws.iam.Policy("publish-sns-policy",
        description="A test policy",
        policy="""{
            "Version": "2012-10-17",
            "Statement": [
                {
                "Action": [
                    "sns:Publish"
                ],
                "Effect": "Allow",
                "Resource": "*"
                }
            ]
        }
    """)
    
    # Attach SNS policy to our lambda role
    role_policy_attachment = aws.iam.RolePolicyAttachment("lambdaRoleAttachment",
        role=lambda_role.name,
        policy_arn=sns_policy.arn)
    
    # Return role so we can use it as a variable
    return lambda_role

def create_topic():
    morning_updates_topic = aws.sns.Topic("morningUpdates")

    # Return it so we can use as lambda environment variable
    return morning_updates_topic

def create_lambda_function(role_arn, morning_updates_arn):
    lambda_function = aws.lambda_.Function("lambdaFunction", 
        code=pulumi.AssetArchive({
            ".": pulumi.FileArchive("./app"),
        }),
        environment={
            "variables": {
                'topic_arn': morning_updates_arn
            },
        },
        runtime="python3.8",
        role=role_arn,
        handler="index.lambda_handler")
    
    return lambda_function


def create_cron_trigger(lambda_function):
    # Create the trigger    
    morningTrigger = aws.cloudwatch.EventRule("morningTrigger",
        description="Trigger lambda at 7 each morning",
        schedule_expression="cron(0 7 * * ? *)")

    # Set the Event Target (our Lambda)
    lambda_target = aws.cloudwatch.EventTarget("lambdaEventTarget",
        rule=morningTrigger.name,
        arn=lambda_function.arn)
    
    # Give permissions for events to invoke Lambda
    event_permission = aws.lambda_.Permission("eventPermission",
        action="lambda:InvokeFunction",
        function=lambda_function.name,
        principal="events.amazonaws.com",
        source_arn=morningTrigger.arn)
    
def subscribe_to_topic(topic_arn):
    morning_updates_sqs_target = aws.sns.TopicSubscription("morningUpdates",
    endpoint="travis@travis.media",
    protocol="email",
    topic=topic_arn)
    
# Call functions in this order
lambda_role = create_lambda_role() # - #1
morning_updates = create_topic() # - #2
lambda_function = create_lambda_function(lambda_role.arn, morning_updates.arn) # - #3
cron_trigger = create_cron_trigger(lambda_function) # - #4
subscribe_to_topic(morning_updates.arn)

