# RelaySMS Gateway Server

RelaySMS Gateway Server is the online router that receives messages from gateway clients and directs them to users' chosen internet platforms.

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Docker](#docker)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Requirements

- **Python:** ≥ 3.8.10
- **Database:** MySQL (≥ 8.0.28), MariaDB, or SQLite
- **External Services:**
  - [RelaySMS Publisher](https://github.com/smswithoutborders/RelaySMS-Publisher) (required)
  - [RelaySMS Bridge](https://github.com/smswithoutborders/RelaySMS-Bridge-Server) (required)
  - IMAP Email Server (optional, for email monitoring)

**Ubuntu Dependencies:**

```bash
sudo apt install python3-dev libmysqlclient-dev make
```

## Installation

### Production

Quick install:

```bash
curl -fsSL https://raw.githubusercontent.com/smswithoutborders/RelaySMS-Gateway-Server/main/install.sh | sudo bash
```

Manage services:

```bash
cd /opt/relaysms/relaysms-gateway-server
./manage.sh {start|stop|restart|status|logs|update}
```

See [INSTALL.md](INSTALL.md) for manual installation and detailed configuration.

### Development

```bash
# Setup environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp template.env .env
# Edit .env as needed

# Build
make grpc-compile

# Start services (use separate terminals)
python3 -m src.imap_listener     # Terminal 1 (optional)
python3 -m src.ftp_server        # Terminal 2
make start-rest-api              # Terminal 3
```

**Quick Development Setup:**

```bash
./scripts/quick-setup.sh && ./scripts/quick-start.sh
```

> [!WARNING]
> Quick setup is for development only. Do not use in production.

## Docker

### Build the Docker Image

```bash
docker build -t relaysms-gateway-server:latest .
```

### Run the Container

```bash
docker run -d \
  --name relaysms-gateway-server \
  --env-file .env \
  -p 5000:5000 -p 5001:5001 \
  -p 2222:2222 -p 60000-65000:60000-65000 \
  -v $(pwd)/data:/gateway_server/data \
  relaysms-gateway-server:latest
```

> [!TIP]
> Update `HOST=0.0.0.0` in `.env` for external container access.

---

## Configuration

Configure via environment variables, either in your shell or a `.env` file.

**To load from `.env`:**

```bash
set -a
source .env
set +a
```

**Or set individually:**

```bash
export HOST=localhost
export PORT=5000
# etc.
```

### Server

- `SSL_SERVER_NAME`: SSL certificate server name (default: `localhost`)
- `HOST`: REST server host (default: `localhost`)
- `PORT`: REST server port (default: `5000`)
- `SSL_PORT`: REST SSL port (default: `5001`)
- `SSL_CERTIFICATE`, `SSL_KEY`, `SSL_PEM`: SSL file paths (optional)

### Publisher gRPC

- `PUBLISHER_GRPC_HOST`: Publisher gRPC server host (default: `127.0.0.1`)
- `PUBLISHER_GRPC_PORT`: Publisher gRPC server port (default: `6000`)

> [!IMPORTANT]
> RelaySMS Publisher must be installed and running. See [RelaySMS Publisher Installation](https://github.com/smswithoutborders/RelaySMS-Publisher/blob/main/INSTALL.md)

### Bridge gRPC

- `BRIDGE_GRPC_HOST`: Bridge gRPC server host (default: `127.0.0.1`)
- `BRIDGE_GRPC_PORT`: Bridge gRPC server port (default: `10000`)

> [!IMPORTANT]
> RelaySMS Bridge must be installed and running. See [RelaySMS Bridge Installation](https://github.com/smswithoutborders/RelaySMS-Bridge-Server/blob/main/INSTALL.md)

### CORS

- `ORIGINS`: Allowed CORS origins (default: `[]`)

### Database

- `MYSQL_HOST`: MySQL host (default: `127.0.0.1`)
- `MYSQL_USER`: MySQL username
- `MYSQL_PASSWORD`: MySQL password
- `MYSQL_DATABASE`: MySQL database (default: `relaysms_gateway_server`)
- `SQLITE_DATABASE_PATH`: SQLite file path (default: `gateway_server.db`)

### IMAP Configuration

- `IMAP_SERVER`: IMAP server hostname
- `IMAP_PORT`: IMAP server port (default: `993`)
- `IMAP_USERNAME`: IMAP username
- `IMAP_PASSWORD`: IMAP password
- `MAIL_FOLDER`: Mail folder to monitor (default: `INBOX`)

> [!NOTE]
> IMAP configuration is optional. Required only if you want to monitor emails for incoming messages.
>
> **Gmail Setup:** Enable IMAP in settings and create an App Password at <https://myaccount.google.com/apppasswords>. See [INSTALL.md](INSTALL.md#imap-email-server-optional) for details.

### FTP Configuration

- `FTP_USERNAME`: FTP username
- `FTP_PASSWORD`: FTP password
- `FTP_IP_ADDRESS`: FTP server IP address (default: `localhost`)
- `FTP_PORT`: FTP server port (default: `2222`)
- `FTP_PASSIVE_PORTS`: FTP passive port range (default: `60000-65000`)
- `FTP_READ_LIMIT`: FTP read limit in bytes (default: `51200`)
- `FTP_WRITE_LIMIT`: FTP write limit in bytes (default: `51200`)
- `FTP_MAX_CON`: Maximum FTP connections (default: `256`)
- `FTP_MAX_CON_PER_IP`: Maximum FTP connections per IP (default: `5`)
- `FTP_DIRECTORY`: FTP directory path (default: `data/ftp_file_store`)

### Security

- `SMTP_ALLOWED_EMAIL_ADDRESSES`: Allowed email addresses for SMTP
- `DISABLE_BRIDGE_PAYLOADS_OVER_HTTP`: Disable bridge payloads over HTTP (default: `false`)

### Logging

- `LOG_LEVEL`: Logging level (default: `info`)

## Documentation

- [Installation Guide](INSTALL.md) - Detailed setup instructions
- [API V3](docs/api_v3.md) - REST API documentation
- [Gateway Client CLI](docs/gateway_clients_cli.md) - CLI documentation

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-branch`
3. Commit your changes
4. Push to your branch
5. Open a pull request

## License

Licensed under the GNU General Public License (GPL). See [LICENSE](LICENSE) for details.
