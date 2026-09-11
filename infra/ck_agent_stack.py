"""Infrastructure for the deployed demo.

A single t3.micro in a public subnet, reachable only from one IP address, with
an instance role that can call exactly two Bedrock actions. That shape is
chosen for a time boxed proof of concept, not for production; the trade-offs
against ECS Fargate are set out in docs/SOLUTION.md.

Two cost decisions are worth naming because both are easy to get wrong:

- `nat_gateways=0`. A CDK Vpc with default settings provisions a NAT Gateway,
  which bills hourly whether or not anything uses it and is the single most
  common surprise on a small account. The instance sits in a public subnet
  with a public IP instead, so it reaches Bedrock directly.
- No load balancer. An ALB costs more per hour than the instance it fronts.
  With one instance and one viewer there is nothing to balance.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from constructs import Construct

REPO_URL = "https://github.com/Kevinau38/ck-agent.git"
APP_PORT = 8000

USER_DATA = f"""#!/bin/bash
set -xe

dnf update -y
dnf install -y git python3.11 python3.11-pip

cd /opt
git clone {REPO_URL}
cd ck-agent

python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# No access keys on this machine. Credentials come from the instance role
# through the metadata service and rotate automatically.
cat > /opt/ck-agent/.env <<'ENVEOF'
AWS_REGION={{REGION}}
AGENT_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
EMBED_MODEL_ID=cohere.embed-english-v3
TOP_K=4
ENVEOF

# data/ is gitignored, so the index and the mock database are built here.
# build_index.py calls Bedrock, which is why the role is attached before boot.
.venv/bin/python ingest/extract.py
.venv/bin/python ingest/build_index.py
.venv/bin/python data/seed_db.py

cat > /etc/systemd/system/ck-agent.service <<'SVCEOF'
[Unit]
Description=CK Agent
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/ck-agent
ExecStart=/opt/ck-agent/.venv/bin/python -m uvicorn api.server:app --host 0.0.0.0 --port {APP_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable --now ck-agent
"""


class CkAgentStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        allowed_cidr: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=1,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )

        sg = ec2.SecurityGroup(
            self,
            "Sg",
            vpc=vpc,
            description="CK Agent web layer",
            allow_all_outbound=True,
        )
        # One source address, one port. No SSH: everything the instance needs
        # to do happens in user data, and Session Manager covers the rest if
        # a shell is ever required.
        sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(allowed_cidr),
            connection=ec2.Port.tcp(APP_PORT),
            description="Chat UI from one developer address only",
        )

        role = iam.Role(
            self,
            "InstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Runtime role for the CK Agent instance",
        )

        # Two actions, not bedrock:*. The application never creates guardrails,
        # knowledge bases or agents, so it has no need to be able to.
        #
        # The resource list is wider than ideal: invoking a model through a
        # cross-region inference profile requires permission on the profile and
        # on the underlying foundation model in whichever region the request is
        # routed to, and a global profile can route anywhere. Pinning to a
        # single model ARN would break the call. A US-scoped profile in
        # us-east-1 would allow a narrower list, which is one more argument for
        # the region choice described in the write-up.
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:*:{self.account}:inference-profile/*",
                ],
            )
        )

        instance = ec2.Instance(
            self,
            "Instance",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            security_group=sg,
            role=role,
            user_data=ec2.UserData.custom(USER_DATA.replace("{REGION}", self.region)),
        )

        # A static address so the demo URL survives a stop/start. Released on
        # cdk destroy along with everything else.
        eip = ec2.CfnEIP(self, "Eip", domain="vpc")
        ec2.CfnEIPAssociation(
            self,
            "EipAssoc",
            allocation_id=eip.attr_allocation_id,
            instance_id=instance.instance_id,
        )

        cdk.CfnOutput(
            self,
            "ChatUrl",
            value=f"http://{eip.ref}:{APP_PORT}",
            description="Open this once the instance has finished booting",
        )
        cdk.CfnOutput(self, "InstanceId", value=instance.instance_id)
        cdk.CfnOutput(self, "AllowedFrom", value=allowed_cidr)
