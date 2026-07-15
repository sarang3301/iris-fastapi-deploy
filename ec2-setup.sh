#!/bin/bash
# ec2-setup.sh
#
# Run this ONCE on a fresh EC2 instance (Amazon Linux 2023) to install
# Docker and get it ready to receive deployments from the CI/CD pipeline.
#
# Usage (from your local machine):
#   scp -i your-key.pem ec2-setup.sh ec2-user@<EC2_HOST>:~/
#   ssh -i your-key.pem ec2-user@<EC2_HOST> "chmod +x ec2-setup.sh && ./ec2-setup.sh"

set -e

echo "Installing Docker..."
sudo dnf install -y docker
sudo systemctl enable docker
sudo systemctl start docker

# Let ec2-user run docker without sudo (log out/in once for this to take effect)
sudo usermod -aG docker ec2-user

echo "Installing AWS CLI (needed to pull from ECR)..."
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    sudo ./aws/install
    rm -rf awscliv2.zip aws
fi

echo "Done. Docker and AWS CLI are installed."
echo "Log out and back in (or run 'newgrp docker') so the docker group membership applies."
