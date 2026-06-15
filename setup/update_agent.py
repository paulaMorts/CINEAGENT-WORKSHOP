"""Update the deployed agent with simplified code."""
import boto3
c = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
resp = c.update_agent_runtime(
    agentRuntimeId='cineagent_runtime-cWZJei3kII',
    roleArn='arn:aws:iam::235251523570:role/BedrockAgentCoreRole',
    networkConfiguration={'networkMode': 'PUBLIC'},
    agentRuntimeArtifact={
        'codeConfiguration': {
            'code': {'s3': {'bucket': 'cineagent-workshop-235251523570', 'prefix': 'agentcore/cineagent-agent.zip'}},
            'runtime': 'PYTHON_3_13',
            'entryPoint': ['entrypoint.py'],
        }
    },
    environmentVariables={
        'MEMORY_ID': 'cineagent_memory-ViHdbl3uK0',
        'OMDB_API_KEY': 'de3d5a9d',
    },
)
print(f"Updated! Status: {resp.get('status')}")
