import boto3
import json

client = boto3.client("bedrock-runtime", region_name="us-east-1")

body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 100,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello Claude"}
            ]
        }
    ]
}

response = client.invoke_model(
    modelId="global.anthropic.claude-sonnet-4-6",
    body=json.dumps(body)
)

result = json.loads(response["body"].read())

print(result)