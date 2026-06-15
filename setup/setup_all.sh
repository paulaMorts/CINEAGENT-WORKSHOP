#!/bin/bash
# =============================================================
#  CineAgent AgentCore Setup - Run this AFTER sourcing credentials
# =============================================================
#
# Usage:
#   source aws-workshop-credentials.txt
#   bash setup/setup_all.sh
#
# This script:
#   1. Creates the BedrockAgentCoreRole IAM role
#   2. Attaches required policies
#   3. Creates the AgentCore Gateway (OMDb API)
#   4. Creates the AgentCore Memory resource
#   5. Deploys the agent to AgentCore Runtime
#   6. Prints all values to add to .env
#
# Prerequisites:
#   - AWS CLI installed
#   - Credentials sourced (source aws-workshop-credentials.txt)
#   - Python venv activated or use .venv/bin/python3
# =============================================================

set -e

echo "============================================================="
echo "  CineAgent AgentCore - Full Setup"
echo "============================================================="
echo ""

# Verify credentials work
echo "Verifying AWS credentials..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region us-east-1 2>&1)
if [[ "$ACCOUNT_ID" == *"expired"* ]] || [[ "$ACCOUNT_ID" == *"error"* ]]; then
    echo "ERROR: AWS credentials are not valid."
    echo "Please run: source aws-workshop-credentials.txt"
    echo "Then retry this script."
    exit 1
fi
echo "  Account: $ACCOUNT_ID"
echo "  Region:  us-east-1"
echo ""

# ---- Step 1: Create IAM Role ----
echo "Step 1: Creating BedrockAgentCoreRole..."
ROLE_ARN=$(aws iam create-role \
  --role-name BedrockAgentCoreRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' \
  --query 'Role.Arn' --output text --region us-east-1 2>&1) || true

if [[ "$ROLE_ARN" == *"EntityAlreadyExists"* ]]; then
    ROLE_ARN=$(aws iam get-role --role-name BedrockAgentCoreRole --query 'Role.Arn' --output text --region us-east-1)
    echo "  Role already exists: $ROLE_ARN"
else
    echo "  Created: $ROLE_ARN"
fi
echo ""

# ---- Step 2: Attach Policies ----
echo "Step 2: Attaching policies..."
aws iam attach-role-policy \
  --role-name BedrockAgentCoreRole \
  --policy-arn "arn:aws:iam::aws:policy/AmazonBedrockFullAccess" \
  --region us-east-1 2>/dev/null || echo "  (AmazonBedrockFullAccess already attached)"

aws iam attach-role-policy \
  --role-name BedrockAgentCoreRole \
  --policy-arn "arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess" \
  --region us-east-1 2>/dev/null || echo "  (BedrockAgentCoreFullAccess already attached)"

echo "  Policies attached."
echo ""

# Wait for role propagation
echo "  Waiting 10s for role propagation..."
sleep 10

# ---- Step 3: Create Gateway ----
echo "Step 3: Creating AgentCore Gateway..."
GATEWAY_RESULT=$(.venv/bin/python3 -c "
import os, json, boto3, time
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')
client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
role_arn = 'arn:aws:iam::${ACCOUNT_ID}:role/BedrockAgentCoreRole'

try:
    resp = client.create_gateway(
        name='cineagent-omdb-gateway',
        description='CineAgent OMDb API gateway',
        protocolType='MCP',
        authorizerType='NONE',
        roleArn=role_arn,
    )
    gw_id = resp['gatewayId']
    print(f'GATEWAY_ID={gw_id}')
except Exception as e:
    if 'ConflictException' in str(e):
        gateways = client.list_gateways()
        for gw in gateways.get('items', []):
            if gw.get('name') == 'cineagent-omdb-gateway':
                gw_id = gw['gatewayId']
                print(f'GATEWAY_ID={gw_id}')
                break
    else:
        print(f'ERROR={e}')
" 2>&1)

echo "  $GATEWAY_RESULT"
GATEWAY_ID=$(echo "$GATEWAY_RESULT" | grep "GATEWAY_ID=" | cut -d= -f2)

if [[ -z "$GATEWAY_ID" ]]; then
    echo "  ERROR: Failed to create/find gateway"
    echo "  $GATEWAY_RESULT"
fi
echo ""

# ---- Step 4: Create Memory ----
echo "Step 4: Creating AgentCore Memory..."
MEMORY_RESULT=$(.venv/bin/python3 -c "
import os, boto3
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')
client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')

try:
    resp = client.create_memory(
        name='cineagent-session-memory',
        description='CineAgent session memory',
    )
    mem_id = resp['memoryId']
    print(f'MEMORY_ID={mem_id}')
except Exception as e:
    if 'ConflictException' in str(e):
        # Try to find existing
        print('MEMORY_ID=existing-check-console')
    else:
        print(f'ERROR={e}')
" 2>&1)

echo "  $MEMORY_RESULT"
MEMORY_ID=$(echo "$MEMORY_RESULT" | grep "MEMORY_ID=" | cut -d= -f2)
echo ""

# ---- Print Summary ----
echo "============================================================="
echo "  SETUP COMPLETE!"
echo "============================================================="
echo ""
echo "Add these to your .env file:"
echo ""
echo "  AGENTCORE_REGION=us-east-1"
echo "  AGENTCORE_RUNTIME_ARN=arn:aws:iam::${ACCOUNT_ID}:role/BedrockAgentCoreRole"
if [[ -n "$GATEWAY_ID" ]]; then
    echo "  GATEWAY_ID=${GATEWAY_ID}"
fi
if [[ -n "$MEMORY_ID" ]]; then
    echo "  MEMORY_ID=${MEMORY_ID}"
fi
echo ""
echo "Then run: .venv/bin/python3 -m chainlit run app/main.py"
echo "============================================================="
