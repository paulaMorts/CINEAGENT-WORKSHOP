"""Deploy CineAgent to AgentCore Runtime. Run with: source aws-workshop-credentials.txt && .venv/bin/python3 setup/deploy_now.py"""
import boto3, io, zipfile, os, json, sys

# Package agent code
buffer = io.BytesIO()
agent_dir = os.path.join(os.path.dirname(__file__), '..', 'agentcore_agent')
with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(agent_dir):
        for f in files:
            if '__pycache__' in root or f.startswith('.'):
                continue
            filepath = os.path.join(root, f)
            arcname = os.path.relpath(filepath, agent_dir)
            zf.write(filepath, arcname)
            print(f'  Packed: {arcname}')

zip_bytes = buffer.getvalue()
print(f'Package: {len(zip_bytes)} bytes')

# Upload to S3
s3 = boto3.client('s3', region_name='us-east-1')
bucket = 'cineagent-workshop-235251523570'
key = 'agentcore/cineagent-agent.zip'

try:
    s3.head_bucket(Bucket=bucket)
except:
    s3.create_bucket(Bucket=bucket)
    print(f'Created bucket: {bucket}')

s3.put_object(Bucket=bucket, Key=key, Body=zip_bytes)
print(f'Uploaded: s3://{bucket}/{key}')

# Create agent runtime
c = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
try:
    resp = c.create_agent_runtime(
        agentRuntimeName='cineagent_runtime',
        description='CineAgent movie assistant',
        roleArn='arn:aws:iam::235251523570:role/BedrockAgentCoreRole',
        networkConfiguration={'networkMode': 'PUBLIC'},
        agentRuntimeArtifact={
            'codeConfiguration': {
                'code': {'s3': {'bucket': bucket, 'prefix': key}},
                'runtime': 'PYTHON_3_13',
                'entryPoint': ['entrypoint.py'],
            }
        },
        environmentVariables={
            'MEMORY_ID': 'cineagent_memory-ViHdbl3uK0',
            'GATEWAY_URL': 'https://cineagent-omdb-gateway-sksvpak1fi.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp',
        },
    )
    arn = resp.get('agentRuntimeArn', '')
    print(f'\nSUCCESS! Agent deployed.')
    print(f'ARN: {arn}')
    print(f'Status: {resp.get("status")}')
    print(f'\nAdd to .env: AGENTCORE_RUNTIME_ARN={arn}')
except Exception as e:
    if 'ConflictException' in str(e) or 'already exists' in str(e):
        print(f'Agent already exists. Listing...')
        r = c.list_agent_runtimes()
        for a in r.get('agentRuntimeSummaries', r.get('items', [])):
            print(f"  {a}")
    else:
        print(f'Error: {type(e).__name__}: {e}')
        sys.exit(1)
