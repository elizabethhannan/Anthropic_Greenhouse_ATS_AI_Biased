import os
import boto3

required = [
    "R2_ENDPOINT",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
]

missing = [name for name in required if not os.getenv(name)]

if missing:
    raise RuntimeError(
        "Missing environment variables: " + ", ".join(missing)
    )

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["R2_ENDPOINT"],
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)

bucket = os.environ["R2_BUCKET"]
key = "connection-test/hello.txt"

s3.put_object(
    Bucket=bucket,
    Key=key,
    Body=b"R2 connection works."
)

response = s3.head_object(
    Bucket=bucket,
    Key=key,
)

print("R2 upload successful.")
print("Bucket:", bucket)
print("Object:", key)
print("Bytes:", response["ContentLength"])
