#!/bin/bash
# EC2 user-data: runs once as root on first boot (Amazon Linux 2023).
set -euo pipefail
exec > >(tee /var/log/user-data.log) 2>&1

# ---- swap (free-tier RAM is tight; this is the safety net) ----
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo "/swapfile none swap sw 0 0" >> /etc/fstab

# ---- docker + compose plugin ----
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user

# Amazon Linux 2023's dnf repo doesn't carry the compose plugin; install it
# directly per Docker's own published release, matching how the compose v2
# plugin is normally distributed.
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# SSM agent ships preinstalled on Amazon Linux 2023 AMIs and starts itself —
# nothing to do here for that.

# ---- clone both apps ----
mkdir -p /opt
cd /opt
git clone https://github.com/connect112/ERPX.git erpx

# Pentrix-share is private — the deploy key is written separately via SSM
# right after this script runs (it needs to exist before this clone can
# succeed), so this script does NOT clone it; see the setup runbook.

echo "user-data bootstrap complete" > /opt/bootstrap-done
