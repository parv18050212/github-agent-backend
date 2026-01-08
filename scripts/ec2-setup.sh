#!/bin/bash

# EC2 Initial Setup Script
# Run this once on your EC2 instance to prepare for deployments

set -e

echo "🚀 Setting up EC2 instance for Repository Analyzer..."

# Update system
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
echo "📦 Installing dependencies..."
sudo apt-get install -y \
    git \
    curl \
    python3.12 \
    python3-pip \
    docker.io \
    docker-compose \
    nginx \
    certbot \
    python3-certbot-nginx

# Install Docker Compose v2
echo "🐳 Installing Docker Compose v2..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version

# Add ubuntu user to docker group
echo "👤 Configuring Docker permissions..."
sudo usermod -aG docker ubuntu
sudo systemctl enable docker
sudo systemctl start docker

# Create application directory
echo "📁 Creating application directory..."
sudo mkdir -p /home/ubuntu/repo-analyzer
sudo chown -R ubuntu:ubuntu /home/ubuntu/repo-analyzer

# Clone repository (you'll need to update this URL)
echo "📥 Cloning repository..."
cd /home/ubuntu/repo-analyzer
read -p "Enter your GitHub repository URL: " REPO_URL
git clone $REPO_URL .

# Create logs directory
mkdir -p logs report

# Configure firewall
echo "🔥 Configuring firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
sudo ufw --force enable

# Configure Nginx reverse proxy
echo "🌐 Configuring Nginx..."
sudo tee /etc/nginx/sites-available/repo-analyzer << 'EOF'
server {
    listen 80;
    server_name _;

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/repo-analyzer /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# Setup SSL (optional - run after DNS is configured)
echo ""
echo "📋 Setup SSL certificate (run after DNS is configured):"
echo "sudo certbot --nginx -d api.yourdomain.com"
echo ""

# Display EC2 instance info
echo ""
echo "✅ EC2 setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Configure GitHub Secrets in your repository settings:"
echo ""
echo "   AWS_ACCESS_KEY_ID=<your-aws-key>"
echo "   AWS_SECRET_ACCESS_KEY=<your-aws-secret>"
echo "   AWS_REGION=<your-region>"
echo "   EC2_SSH_KEY=<your-private-key-content>"
echo "   EC2_HOST=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "   EC2_USER=ubuntu"
echo "   SUPABASE_URL=<your-supabase-url>"
echo "   SUPABASE_KEY=<your-supabase-key>"
echo "   OPENAI_API_KEY=<your-openai-key>"
echo "   CORS_ORIGINS=<your-frontend-urls>"
echo ""
echo "2. Log out and log back in for Docker group changes to take effect"
echo "3. Push code to GitHub main branch to trigger deployment"
echo ""
echo "🌐 Your EC2 Public IP: $(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "📡 API will be available at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
