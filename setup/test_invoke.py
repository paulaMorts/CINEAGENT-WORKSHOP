"""Test invoking the deployed runtime agent."""
import boto3, json
c = boto3.client('bedrock-agentcore', region_name='us-east-1')
try:
    r = c.invoke_agent_runtime(
        agentRuntimeArn='arn:aws:bedrock-agentcore:us-east-1:235251523570:runtime/cineagent_v2-7OBSbhHskj',
        payload=json.dumps({'prompt': 'hi', 'session_id': 'test1'}),
        contentType='application/json',
        accept='application/json',
    )
    body = r.get('body', b'')
    if hasattr(body, 'read'):
        body = body.read()
    if isinstance(body, bytes):
        body = body.decode()
    print('SUCCESS:', body[:300])
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
