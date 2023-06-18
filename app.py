#!/usr/bin/env python3
import os

import aws_cdk as cdk

from group_assign.group_assign_stack import GroupAssignStack

from aws_cdk import (
    aws_s3 as s3,
    aws_iam as iam,
    aws_s3_notifications,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks
)

app = cdk.App()

class TranslatePipelineStack(cdk.Stack):

    def __init__(self, scope: cdk.Stack, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create S3 bucket
        bucket = s3.Bucket(self, "TranslateBucket")

        # Create IAM role for Lambda functionpp
        role = iam.Role(self, "LambdaRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))

        # Create Lambda function
        lambda_function = _lambda.Function(
            self, "LambdaHandler",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("lambda"),
            handler="handler.lambda_handler",
            role=role,
            
        )

        # Allow Lambda function to access S3 bucket
        bucket.grant_read_write(lambda_function)

        # Create S3 event for Lambda function
        bucket.add_event_notification(s3.EventType.OBJECT_CREATED, aws_s3_notifications.LambdaDestination(lambda_function))

        # Create Step Functions
        transcribe_task = sfn_tasks.CallAwsService(
            self, "Transcribe",
            service="transcribe",
            action="startTranscriptionJob",
            parameters={
                "TranscriptionJobName": sfn.JsonPath.string_at("$.TranscriptionJobName"),
                "LanguageCode": "es-US",
                "Media": {
                    "MediaFileUri": sfn.JsonPath.string_at("$.MediaFileUri")
                },
                "OutputBucketName": sfn.JsonPath.string_at("$.OutputBucketName")
            },
            result_path="$.TranscribeResult",
            iam_resources=["arn:aws:transcribe:*:*:*"]
            )

        translate_task = sfn_tasks.CallAwsService(
            self, "Translate",
            service="translate",
            action="translateText",
            parameters={
                "Text": sfn.JsonPath.string_at("$.TranscribeResult.Transcript.Text"),
                "SourceLanguageCode": "es",
                "TargetLanguageCode": "en"
            },
            result_path="$.TranslateResult",
            iam_resources=["arn:aws:translate:*:*:*"]
        )

        polly_task = sfn_tasks.CallAwsService(
            self, "Polly",
            service="polly",
            action="synthesizeSpeech",
            parameters={
                "OutputFormat": "mp3",
                "Text": sfn.JsonPath.string_at("$.TranslateResult.TranslatedText"),
                "VoiceId": "Fran"
            },
            result_path="$.PollyResult",
            iam_resources=["arn:aws:polly:*:*:*"]
        )

        definition = transcribe_task.next(translate_task).next(polly_task)

        state_machine = sfn.StateMachine(
            self, "StateMachine",
            definition=definition,
            timeout=cdk.Duration.minutes(5)
        )
        state_machine.grant_start_execution(lambda_function)
        
TranslatePipelineStack(app, "TranslatePipelineStack")

app.synth()
