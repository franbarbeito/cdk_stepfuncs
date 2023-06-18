import json
import boto3
from urllib.parse import unquote_plus

s3_client = boto3.client('s3')
transcribe = boto3.client('transcribe')
translate = boto3.client('translate')
polly = boto3.client('polly')

def lambda_handler(event, context):
    # Extract the bucket name and file key from the event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = unquote_plus(event['Records'][0]['s3']['object']['key'])

    # Start a transcription job
    transcribe.start_transcription_job(
        TranscriptionJobName=key,
        Media={'MediaFileUri': f's3://{bucket}/{key}'},
        MediaFormat='mp3',
        LanguageCode='es-US'
    )

    while True:
        response = transcribe.get_transcription_job(TranscriptionJobName=key)
        status = response['TranscriptionJob']['TranscriptionJobStatus']
        if status in ['COMPLETED', 'FAILED']:
            break
        print('Waiting for transcription job to finish...')
        time.sleep(10)  # Wait for 10 seconds


    transcript_file_uri = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
    transcript_text = json.loads(s3_client.get_object(Bucket=bucket, Key=transcript_file_uri)['Body'].read().decode('utf-8'))['results']['transcripts'][0]['transcript']
    result = translate.translate_text(Text=transcript_text, SourceLanguageCode='es', TargetLanguageCode='en')
    response = polly.synthesize_speech(Text=result['TranslatedText'], OutputFormat='mp3', VoiceId='Joanna')

    s3_client.put_object(Body=response['AudioStream'].read(), Bucket=bucket, Key=f'translations/{key}_en.mp3')

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
