# Laravel API Server for CSV Sync

This folder now contains an API-only Laravel implementation for:

- `POST /api/v1/upload-csv`
- API key authentication using `X-API-Key`
- source IP whitelist
- CSV-only validation
- filename/path traversal protection
- idempotency by filename + SHA-256

## Linux server spec (same as production)

- OS: Ubuntu Server 22.04 LTS or 24.04 LTS
- Web stack: Nginx + PHP 8.3 FPM
- Database: MariaDB 12.3.2 (or latest stable MariaDB available in your repo)
- Runtime: Laravel 11 (API-only routes)
- TLS: HTTPS only
- Firewall: only Windows client IP can access API port 443

## 1) Install system packages on Linux

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget unzip git ca-certificates software-properties-common
sudo add-apt-repository ppa:ondrej/php -y
sudo apt update
sudo apt install -y nginx php8.3-fpm php8.3-cli php8.3-mysql php8.3-xml php8.3-curl php8.3-mbstring php8.3-zip php8.3-bcmath
sudo apt install -y mariadb-server
```

Install Composer:

```bash
cd /tmp
php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');"
php composer-setup.php
sudo mv composer.phar /usr/local/bin/composer
composer --version
```

## 2) Create Laravel base project on server

Run this one time on each Linux server:

```bash
sudo mkdir -p /srv/app
sudo chown -R $USER:$USER /srv/app
cd /srv/app
composer create-project laravel/laravel server "^11.0"
```

Then copy this repository `server` code into `/srv/app/server` and overwrite matching files.

## 3) Configure environment

```bash
cd /srv/app/server
cp .env.example .env
php artisan key:generate
```

Set important values in `.env`:

```env
APP_ENV=production
APP_DEBUG=false
APP_URL=https://server-1.example.com

DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=csv_sync
DB_USERNAME=csv_sync_user
DB_PASSWORD=replace-with-strong-db-password

CSV_SYNC_API_KEY=replace-with-a-long-random-api-key
CSV_SYNC_ALLOWED_IPS=192.168.1.50
CSV_SYNC_UPLOAD_ROOT=/srv/uploads/csv
CSV_SYNC_DEFAULT_UPLOAD_DIRECTORY=csv
```

Create upload directory permissions:

```bash
sudo mkdir -p /srv/uploads/csv
sudo chown -R www-data:www-data /srv/uploads
sudo chmod -R 775 /srv/uploads
```

## 4) Database setup (if needed)

```bash
sudo mysql
```

```sql
CREATE DATABASE csv_sync;
CREATE USER 'csv_sync_user'@'localhost' IDENTIFIED BY 'replace-with-strong-db-password';
GRANT ALL PRIVILEGES ON csv_sync.* TO 'csv_sync_user'@'localhost';
FLUSH PRIVILEGES;
```

## 5) Run API with PHP-FPM + Nginx

Nginx site config example:

```nginx
server {
    listen 443 ssl http2;
    server_name server-1.example.com;

    root /srv/app/server/public;
    index index.php;

    ssl_certificate /etc/letsencrypt/live/server-1.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/server-1.example.com/privkey.pem;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php8.3-fpm.sock;
    }

    location ~ /\.ht {
        deny all;
    }
}
```

Reload services:

```bash
sudo systemctl enable nginx php8.3-fpm
sudo systemctl restart php8.3-fpm
sudo systemctl restart nginx
```

## 6) Firewall (strict whitelist)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.1.50 to any port 443 proto tcp
sudo ufw allow from ADMIN_IP to any port 22 proto tcp
sudo ufw enable
```

When rollout is complete, SSH can be restricted further or closed based on your operations policy.

## API request example

```bash
curl -X POST "https://server-1.example.com/api/v1/upload-csv" \
  -H "X-API-Key: replace-with-a-long-random-api-key" \
  -F "directory=csv" \
  -F "file=@/path/to/example.csv"
```

Success response:

```json
{
  "status": "success",
  "filename": "example.csv",
  "size": 12345,
  "sha256": "..."
}
```

If file already exists with same checksum, response is `already_exists` with HTTP 200.
If filename is same but checksum differs, response is HTTP 409 `conflict`.
