# BAMIS Fraud Detection Platform - Deployment Guide

## 🚀 Production Deployment Guide

This guide provides step-by-step instructions for deploying the BAMIS Enhanced Banking Fraud Detection Platform to production environments.

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04+ / CentOS 8+ / RHEL 8+
- **RAM**: 8GB minimum (16GB recommended)
- **Storage**: 50GB minimum (SSD recommended)
- **CPU**: 4 cores minimum (8 cores recommended)
- **Network**: Stable internet connection for AI features

### Software Requirements
- Python 3.11+
- PostgreSQL 13+
- Redis 6+ (for caching)
- Nginx (web server)
- Supervisor (process management)
- SSL Certificate

## 🔧 Server Setup

### 1. Update System
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3.11-dev
sudo apt install -y postgresql postgresql-contrib redis-server nginx supervisor
sudo apt install -y git curl wget unzip
```

### 2. Create Application User
```bash
sudo adduser bamis
sudo usermod -aG sudo bamis
su - bamis
```

### 3. Setup PostgreSQL
```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE bamis_fraud_db;
CREATE USER bamis_user WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE bamis_fraud_db TO bamis_user;
ALTER USER bamis_user CREATEDB;
\q
```

### 4. Configure PostgreSQL
Edit `/etc/postgresql/13/main/postgresql.conf`:
```
listen_addresses = 'localhost'
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
```

Edit `/etc/postgresql/13/main/pg_hba.conf`:
```
local   bamis_fraud_db  bamis_user                md5
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
sudo systemctl enable postgresql
```

## 📦 Application Deployment

### 1. Clone Repository
```bash
cd /home/bamis
git clone <repository-url> bamis-fraud-platform
cd bamis-fraud-platform
```

### 2. Create Virtual Environment
```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

### 4. Environment Configuration
Create `/home/bamis/bamis-fraud-platform/.env`:
```env
# Django Settings
SECRET_KEY=your-very-secure-secret-key-here-change-this
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,localhost

# Database
DATABASE_URL=postgresql://bamis_user:secure_password_here@localhost:5432/bamis_fraud_db

# API Keys
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Security
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Email (for notifications)
EMAIL_HOST=smtp.your-email-provider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@domain.com
EMAIL_HOST_PASSWORD=your-email-password

# Redis (for caching)
REDIS_URL=redis://localhost:6379/0
```

### 5. Database Migration
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

### 6. Test Application
```bash
python manage.py runserver 0.0.0.0:8000
```

## 🌐 Web Server Configuration

### 1. Gunicorn Configuration
Create `/home/bamis/bamis-fraud-platform/gunicorn.conf.py`:
```python
bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
user = "bamis"
group = "bamis"
tmp_upload_dir = None
errorlog = "/home/bamis/logs/gunicorn_error.log"
accesslog = "/home/bamis/logs/gunicorn_access.log"
loglevel = "info"
```

### 2. Supervisor Configuration
Create `/etc/supervisor/conf.d/bamis-fraud.conf`:
```ini
[program:bamis-fraud]
command=/home/bamis/bamis-fraud-platform/venv/bin/gunicorn banking_fraud_platform.wsgi:application -c /home/bamis/bamis-fraud-platform/gunicorn.conf.py
directory=/home/bamis/bamis-fraud-platform
user=bamis
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/home/bamis/logs/supervisor.log
environment=PATH="/home/bamis/bamis-fraud-platform/venv/bin"
```

### 3. Create Log Directory
```bash
mkdir -p /home/bamis/logs
sudo chown bamis:bamis /home/bamis/logs
```

### 4. Start Supervisor
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start bamis-fraud
sudo supervisorctl status
```

### 5. Nginx Configuration
Create `/etc/nginx/sites-available/bamis-fraud`:
```nginx
upstream bamis_fraud {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;

    client_max_body_size 100M;

    location /static/ {
        alias /home/bamis/bamis-fraud-platform/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /home/bamis/bamis-fraud-platform/media/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://bamis_fraud;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
```

### 6. Enable Nginx Site
```bash
sudo ln -s /etc/nginx/sites-available/bamis-fraud /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

## 🔒 SSL Certificate Setup

### Using Let's Encrypt (Recommended)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

### Auto-renewal
```bash
sudo crontab -e
```
Add:
```
0 12 * * * /usr/bin/certbot renew --quiet
```

## 📊 Monitoring & Logging

### 1. Log Rotation
Create `/etc/logrotate.d/bamis-fraud`:
```
/home/bamis/logs/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 bamis bamis
    postrotate
        supervisorctl restart bamis-fraud
    endscript
}
```

### 2. System Monitoring
Install monitoring tools:
```bash
sudo apt install htop iotop nethogs
```

### 3. Application Monitoring
Add to Django settings:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/home/bamis/logs/django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
```

## 🔄 Backup Strategy

### 1. Database Backup Script
Create `/home/bamis/scripts/backup_db.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/home/bamis/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="bamis_fraud_db"
DB_USER="bamis_user"

mkdir -p $BACKUP_DIR

pg_dump -U $DB_USER -h localhost $DB_NAME | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Keep only last 30 days of backups
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +30 -delete
```

### 2. Application Backup Script
Create `/home/bamis/scripts/backup_app.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/home/bamis/backups"
DATE=$(date +%Y%m%d_%H%M%S)
APP_DIR="/home/bamis/bamis-fraud-platform"

mkdir -p $BACKUP_DIR

tar -czf $BACKUP_DIR/app_backup_$DATE.tar.gz \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    $APP_DIR

# Keep only last 7 days of app backups
find $BACKUP_DIR -name "app_backup_*.tar.gz" -mtime +7 -delete
```

### 3. Automated Backups
```bash
chmod +x /home/bamis/scripts/*.sh
crontab -e
```
Add:
```
0 2 * * * /home/bamis/scripts/backup_db.sh
0 3 * * 0 /home/bamis/scripts/backup_app.sh
```

## 🔧 Performance Optimization

### 1. Redis Configuration
Edit `/etc/redis/redis.conf`:
```
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### 2. PostgreSQL Optimization
Edit `/etc/postgresql/13/main/postgresql.conf`:
```
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
```

### 3. Django Optimization
Add to settings:
```python
# Caching
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Database optimization
DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['OPTIONS'] = {
    'MAX_CONNS': 20,
    'MIN_CONNS': 5,
}
```

## 🚨 Security Hardening

### 1. Firewall Configuration
```bash
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw deny 8000
```

### 2. Fail2Ban Setup
```bash
sudo apt install fail2ban
```

Create `/etc/fail2ban/jail.local`:
```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled = true
```

### 3. System Updates
```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

## 📈 Health Checks

### 1. Application Health Check
Create `/home/bamis/scripts/health_check.sh`:
```bash
#!/bin/bash
URL="https://your-domain.com/health/"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" $URL)

if [ $STATUS -eq 200 ]; then
    echo "Application is healthy"
    exit 0
else
    echo "Application health check failed: $STATUS"
    # Restart application
    sudo supervisorctl restart bamis-fraud
    exit 1
fi
```

### 2. Monitoring Cron
```bash
*/5 * * * * /home/bamis/scripts/health_check.sh >> /home/bamis/logs/health_check.log 2>&1
```

## 🔄 Deployment Updates

### 1. Update Script
Create `/home/bamis/scripts/deploy.sh`:
```bash
#!/bin/bash
cd /home/bamis/bamis-fraud-platform

# Backup current version
git stash

# Pull latest changes
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart application
sudo supervisorctl restart bamis-fraud

echo "Deployment completed successfully"
```

### 2. Zero-Downtime Deployment
For zero-downtime deployments, consider using:
- Blue-green deployment
- Rolling updates with multiple instances
- Load balancer configuration

## 📞 Troubleshooting

### Common Issues

1. **Application won't start**
   ```bash
   sudo supervisorctl status
   tail -f /home/bamis/logs/supervisor.log
   ```

2. **Database connection issues**
   ```bash
   sudo -u postgres psql -c "SELECT version();"
   python manage.py dbshell
   ```

3. **Static files not loading**
   ```bash
   python manage.py collectstatic --noinput
   sudo nginx -t
   ```

4. **SSL certificate issues**
   ```bash
   sudo certbot certificates
   sudo nginx -t
   ```

### Log Locations
- Application: `/home/bamis/logs/`
- Nginx: `/var/log/nginx/`
- PostgreSQL: `/var/log/postgresql/`
- System: `/var/log/syslog`

## 📋 Post-Deployment Checklist

- [ ] Application accessible via HTTPS
- [ ] SSL certificate valid and auto-renewing
- [ ] Database backups working
- [ ] Monitoring and logging configured
- [ ] Security headers present
- [ ] Performance optimizations applied
- [ ] Health checks functioning
- [ ] Error pages customized
- [ ] Admin user created
- [ ] Sample data loaded (if needed)
- [ ] Documentation updated
- [ ] Team trained on deployment

## 🎯 Production Readiness

Your BAMIS Fraud Detection Platform is now production-ready with:
- High availability configuration
- Automated backups
- Security hardening
- Performance optimization
- Monitoring and alerting
- Scalable architecture

For additional support or advanced configurations, contact the BAMIS technical team.

---

**© 2024 BAMIS. All rights reserved.**

