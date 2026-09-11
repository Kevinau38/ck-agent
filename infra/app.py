#!/usr/bin/env python3
"""CDK entry point.

The address allowed to reach the chat UI is read from CK_ALLOWED_IP so it is
not committed to the repository, and because it changes whenever the developer
moves network. Synthesis works without it; deployment does not.
"""

import os

import aws_cdk as cdk

from ck_agent_stack import CkAgentStack

app = cdk.App()

allowed_ip = os.getenv("CK_ALLOWED_IP", "127.0.0.1")

CkAgentStack(
    app,
    "CkAgentStack",
    allowed_cidr=f"{allowed_ip}/32",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", "ap-southeast-1"),
    ),
    description="Deployed demo for the Cloud Kinetics SE intern assignment",
)

app.synth()
