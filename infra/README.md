# Infrastructure

CDK stack for the deployed demo. One t3.micro in a public subnet, reachable
only from a single IP address, with an instance role scoped to two Bedrock
actions.

## Synthesise (no AWS calls, no cost)

```powershell
cd infra
cdk synth
```

This writes a CloudFormation template to `cdk.out/`. It is the cheapest way to
check the stack is valid.

## Deploy

```powershell
$env:CK_ALLOWED_IP = (Invoke-RestMethod https://checkip.amazonaws.com).Trim()
cd infra
cdk bootstrap
cdk deploy
```

`cdk bootstrap` is a one-off per account and region. The stack outputs a
`ChatUrl`; the instance needs three or four minutes after the stack completes
to install dependencies and build the index before that URL responds.

## Tear down

```powershell
cdk destroy
```

Nothing here is free while it runs. Destroy the stack after recording.

## Cost

Roughly USD 0.012 per hour for the instance. The VPC has no NAT Gateway and
there is no load balancer, which are the two components that would otherwise
dominate the bill.
