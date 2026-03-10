# Phase 2: Layered Terraform Deployment

This directory contains a **layered Terraform configuration** for deploying GitHub Archive Phase 2 processing infrastructure. Layers allow faster deployments by only applying changed resources.

## Directory Structure

```
terraform/
├── layers/
│   ├── 01_static/         # Service accounts, buckets, IAM (apply once)
│   ├── 02_first_time/     # API enabling, Artifact Registry (first-time only)
│   └── 03_operational/    # Cloud Run, Eventarc (daily updates)
└── environments/
    ├── dev/               # Dev environment variables
    └── prod/              # Prod environment variables
```

## Layers Overview

| Layer | Resources | When to Apply | Apply Frequency |
|-------|-----------|---------------|-----------------|
| **01_static** | • Service accounts (3)<br>• Project IAM (5 bindings)<br>• Staging bucket<br>• Bucket IAM (4 bindings) | Once, rarely changes | Once |
| **02_first_time** | • Google Cloud APIs (8)<br>• Artifact Registry repo | New project/environment only | Once |
| **03_operational** | • Cloud Run service<br>• Eventarc triggers (2)<br>• Cloud Run IAM | Code updates, config changes | Daily/Weekly |

## Usage

### First-Time Setup (All Layers)

```bash
cd infrastructure/phase2_process_files/scripts
./deploy.sh --layer all
```

### Daily Code Updates (Operational Layer Only)

```bash
# Deploy with new image tag
./deploy.sh --layer operational --image-tag v1.2.3

# Deploy latest
./deploy.sh --layer operational
```

### IAM/Bucket Changes (Static Layer Only)

```bash
./deploy.sh --layer static
```

### Plan Changes Without Applying

```bash
./deploy.sh --layer operational --plan-only
```

### Show Outputs

```bash
# All layers
./deploy.sh --outputs-only --layer all

# Single layer
./deploy.sh --outputs-only --layer operational
```

## Layer Dependencies

```
02_first_time ────┐
                   ├───> 03_operational
01_static ────────┘
```

- Layer 03 reads outputs from Layers 01 and 02 via `terraform_remote_state`
- Layers 01 and 02 are independent of each other

## Terraform State

Each layer has its own state file:

```
gs://PROJECT_ID-terraform-state/
├── terraform/state/phase2-static/         # Layer 01
├── terraform/state/phase2-first-time/     # Layer 02
└── terraform/state/phase2-operational/    # Layer 03
```

## Environment Variables

Edit `environments/dev/terraform.tfvars` or `environments/prod/terraform.tfvars`:

```hcl
project_id            = "dev-dataprocessing-489305"
region                = "us-central1"
environment           = "dev"
terraform_state_bucket = "dev-dataprocessing-489305-terraform-state"
landing_bucket_name    = "dev-dataprocessing-489305-dev-github-archive-landing"
staging_retention_days = 7
processor_memory       = 4
processor_cpu          = 2
max_instances          = 10
chunksize              = 100000
```

## Command Reference

| Option | Description |
|--------|-------------|
| `--layer all` | Deploy all layers (first-time setup) |
| `--layer static` | Deploy Layer 01 only |
| `--layer first-time` | Deploy Layer 02 only |
| `--layer operational` | Deploy Layer 03 only |
| `--env ENV` | Set environment (dev/prod) |
| `--image-tag TAG` | Docker image tag to deploy |
| `--skip-build` | Skip Docker build |
| `--plan-only` | Plan without apply |
| `--destroy` | Destroy resources |
| `--outputs-only` | Show outputs |
| `--help` | Show help message |

## Examples

```bash
# First time: Deploy everything
./deploy.sh --layer all

# Daily: Deploy new code with version tag
./deploy.sh --layer operational --image-tag v1.2.3

# Testing: Plan changes without applying
./deploy.sh --layer operational --plan-only

# Debug: Show current outputs
./deploy.sh --outputs-only --layer all

# Production deployment
./deploy.sh --layer operational --env prod --image-tag v1.2.3
```

## Benefits of Layered Approach

1. **Faster Deployments**: Only apply changed resources
2. **Safer Operations**: Separate state files reduce blast radius
3. **Clear Separation**: Static vs operational resources
4. **Parallel Development**: Teams can work on different layers independently
5. **Easier Debugging**: Smaller state files are easier to inspect
