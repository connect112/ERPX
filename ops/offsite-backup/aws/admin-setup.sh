#!/usr/bin/env bash
# One-time AWS setup for the Pentrix/ERPX off-server backup bucket.
# Run by an AWS identity that is authorized for account 373384939117
# (AWS CloudShell signed in as the account owner/admin works well).
# Needs: s3:CreateBucket, s3:PutBucket*, iam:PutRolePolicy.
# Creates ONE private bucket and ONE inline role policy. Nothing else.
set -euo pipefail

BUCKET=pentrix-erpx-backups-373384939117
REGION=us-east-1
ROLE=pentrix-erpx-ec2-ssm-role

[ "$(aws sts get-caller-identity --query Account --output text)" = "373384939117" ] || { echo "wrong account"; exit 1; }

aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-ownership-controls --bucket "$BUCKET" \
  --ownership-controls 'Rules=[{ObjectOwnership=BucketOwnerEnforced}]'
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}'
aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-policy --bucket "$BUCKET" --policy file://bucket-policy.json
aws s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" --lifecycle-configuration file://lifecycle.json
aws iam put-role-policy --role-name "$ROLE" --policy-name pentrix-erpx-offsite-backup-write \
  --policy-document file://iam-policy-instance-role.json

echo "--- verify ---"
aws s3api get-public-access-block --bucket "$BUCKET"
aws s3api get-bucket-versioning --bucket "$BUCKET"
aws s3api get-bucket-encryption --bucket "$BUCKET" --query 'ServerSideEncryptionConfiguration.Rules[0].ApplyServerSideEncryptionByDefault'
aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET" --query 'Rules[].[ID,Expiration.Days]' --output text
aws iam get-role-policy --role-name "$ROLE" --policy-name pentrix-erpx-offsite-backup-write --query PolicyName
