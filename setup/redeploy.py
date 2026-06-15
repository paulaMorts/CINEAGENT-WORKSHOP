"""Redeploy CineAgent runtime with minimal deps."""
import boto3, io, zipfile, os, json

# Package
buffer = io.BytesIO()
agent_dir = os.path.join(os.path.dirname(__file__), '..', 'agentcore_agent')
with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, _, files in os.walk(agent_dir):
        for f in files:
            if '__pycache__' in root or f.startswith('.'):
                continue
            fp = os.path.join(root, f)
            zf.write(fp, os.path.relpath(fp, agent_dir))
zip_bytes = buffer.getvalue()
print(f'Package: {len(zip_bytes)} bytes')

# Upload
s3 = boto3.client('s3', region_name='us-east-1')
s3.put_object(Bucket='cineagent-workshop-235251523570', Key='agentcore/cineagent-agent.zip', Body=zip_bytes)
print('Uploaded')

# Create runtime
c = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
resp = c.create_agent_runtime(
    agentRuntimeName='cineagent_v2',
    description='CineAgent v2',
    roleArn='arn:aws:iam::235251523570:role/BedrockAgentCoreRole',
    networkConfiguration={'networkMode': 'PUBLIC'},
    agentRuntimeArtifact={'codeConfiguration': {
        'code': {'s3': {'bucket': 'cineagent-workshop-235251523570', 'prefix': 'agentcore/cineagent-agent.zip'}},
        'runtime': 'PYTHON_3_13',
        'entryPoint': ['entrypoint.py'],
    }},
    environmentVariables={'MEMORY_ID': 'cineagent_memory-ViHdbl3uK0', 'OMDB_API_KEY': 'de3d5a9d'},
)
print(f"ARN: {resp.get('agentRuntimeArn')}")
print(f"Status: {resp.get('status')}")
