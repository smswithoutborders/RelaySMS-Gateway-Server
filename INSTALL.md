# Installation Guide

## Automated Installation

```bash
sudo ./install.sh
```

This will:

- Install system dependencies
- Clone repository to `/opt/relaysms/relaysms-gateway-server`
- Setup Python virtualenv
- Compile gRPC protos
- Install and enable systemd services

## Manual Installation

### Install Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    libmariadb-dev git curl make
```

### Clone Repository

```bash
sudo git clone https://github.com/smswithoutborders/RelaySMS-Gateway-Server.git \
    /opt/relaysms/relaysms-gateway-server
cd /opt/relaysms/relaysms-gateway-server
```

### Setup Python Environment

```bash
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```

### Build Application

```bash
source venv/bin/activate
make grpc-compile
```

This will:

- Download publisher and bridge proto files
- Compile gRPC protos

### Configure Environment

```bash
cp template.env .env
vim .env
```

Edit the `.env` file to configure:

- Database settings (MySQL or SQLite)
- Publisher gRPC connection settings
- Bridge gRPC connection settings
- Server ports and hosts
- IMAP settings for email monitoring
- FTP server settings

### Initialize Runtime

```bash
mkdir -p data/ftp_file_store
set -a && source .env && set +a
# Database will be created automatically on first run
```

### Install Services

```bash
sudo cp relaysms-gateway-server.target relaysms-gateway-server-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable relaysms-gateway-server.target
sudo systemctl start relaysms-gateway-server.target
```

## Service Management

```bash
./manage.sh start       # Start all services
./manage.sh stop        # Stop all services
./manage.sh restart     # Restart all services
./manage.sh status      # Check status
./manage.sh logs        # View logs
./manage.sh enable      # Enable on boot
./manage.sh disable     # Disable on boot
./manage.sh update      # Update installation
./manage.sh uninstall   # Remove installation
```

## Configuration

Edit `/opt/relaysms/relaysms-gateway-server/.env`:

### Server

Configure REST API server hosts and ports:

```bash
# REST API
HOST=127.0.0.1
PORT=5000
SSL_PORT=5001

# SSL Configuration (optional)
SSL_CERTIFICATE=/path/to/certificate.crt
SSL_KEY=/path/to/private.key
SSL_PEM=/path/to/certificate.pem
SSL_SERVER_NAME=localhost
```

### Publisher Connection

Configure connection to RelaySMS Publisher:

```bash
PUBLISHER_GRPC_HOST=127.0.0.1
PUBLISHER_GRPC_PORT=6000
```

### Bridge Connection

Configure connection to RelaySMS Bridge:

```bash
BRIDGE_GRPC_HOST=127.0.0.1
BRIDGE_GRPC_PORT=10000
```

### Database

Choose between MySQL and SQLite:

**SQLite (Default):**

```bash
SQLITE_DATABASE_PATH=gateway_server.db
# Leave MySQL settings empty
```

**MySQL:**

```bash
MYSQL_HOST=127.0.0.1
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=relaysms_gateway_server
# Leave SQLITE_DATABASE_PATH empty
```

### IMAP Configuration

Configure IMAP settings for email monitoring:

```bash
IMAP_SERVER=imap.example.com
IMAP_PORT=993
IMAP_USERNAME=your_email@example.com
IMAP_PASSWORD=your_password
MAIL_FOLDER=INBOX
```

### FTP Configuration

Configure FTP server settings:

```bash
FTP_USERNAME=your_ftp_user
FTP_PASSWORD=your_ftp_password
FTP_IP_ADDRESS=localhost
FTP_PORT=2222
FTP_PASSIVE_PORTS=60000-65000
FTP_READ_LIMIT=51200
FTP_WRITE_LIMIT=51200
FTP_MAX_CON=256
FTP_MAX_CON_PER_IP=5
FTP_DIRECTORY=data/ftp_file_store
```

### Security

Configure security settings:

```bash
SMTP_ALLOWED_EMAIL_ADDRESSES=allowed1@example.com,allowed2@example.com
DISABLE_BRIDGE_PAYLOADS_OVER_HTTP=false
```

### CORS

Configure allowed CORS origins:

```bash
ORIGINS=["http://localhost:3000","https://example.com"]
```

## Services

- `relaysms-gateway-server-rest.service` - REST API (default port 5000, SSL port 5001)
- `relaysms-gateway-server-imap.service` - IMAP Listener for email monitoring
- `relaysms-gateway-server-ftp.service` - FTP Server for file transfers
- `relaysms-gateway-server.target` - Service group

## File Locations

- Installation: `/opt/relaysms/relaysms-gateway-server/`
- Configuration: `/opt/relaysms/relaysms-gateway-server/.env`
- Database: `/opt/relaysms/relaysms-gateway-server/gateway_server.db`
- FTP Storage: `/opt/relaysms/relaysms-gateway-server/data/ftp_file_store/`
- Service files: `/etc/systemd/system/relaysms-gateway-server*`

## External Dependencies

### RelaySMS Publisher (Required)

The Gateway Server requires a running instance of RelaySMS Publisher for publishing content to online platforms.

**Installation:**

See [RelaySMS Publisher Installation Guide](https://github.com/smswithoutborders/RelaySMS-Publisher/blob/main/INSTALL.md)

Quick install:

```bash
curl -fsSL https://raw.githubusercontent.com/smswithoutborders/RelaySMS-Publisher/main/install.sh | sudo bash
```

**Configuration:**

Ensure the Publisher gRPC server is accessible and update the `PUBLISHER_GRPC_HOST` and `PUBLISHER_GRPC_PORT` variables in the Gateway Server's `.env` file accordingly.

### RelaySMS Bridge (Required)

The Gateway Server requires a running instance of RelaySMS Bridge for publishing content to email bridges.

**Installation:**

See [RelaySMS Bridge Installation Guide](https://github.com/smswithoutborders/RelaySMS-Bridge-Server/blob/main/INSTALL.md)

**Configuration:**

Ensure the Bridge gRPC server is accessible and update the `BRIDGE_GRPC_HOST` and `BRIDGE_GRPC_PORT` variables in the Gateway Server's `.env` file accordingly.

### IMAP Email Server (Optional)

If you want to use the IMAP listener feature, you'll need access to an email account with IMAP enabled.

**Gmail Setup:**

1. Enable IMAP in Gmail settings
2. Create an App Password:
   - Visit: <https://myaccount.google.com/apppasswords>
   - Sign in with your Google account
   - Select "Mail" as the app and "Other" as the device
   - Generate an app password
3. Use the generated app password as `IMAP_PASSWORD` in `.env`

**Other Email Providers:**

Consult your email provider's documentation for IMAP server details and authentication requirements.
