# RelaySMS Gateway Server

RelaySMS Gateway Server is the online router that receives messages from gateway clients and directs them to users' chosen internet platforms.

## Table of Contents

1. [Quick Start](#quick-start)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [References](#references)
6. [Contributing](#contributing)
7. [License](#license)

## Quick Start

> [!NOTE]
>
> Ensure all [system dependencies](#system-requirements) are installed before running setup scripts.

For development, use the provided scripts:

```bash
source scripts/quick-setup.sh && ./scripts/quick-start.sh
```

- `quick-setup`:

  - Creates a Python virtual environment (if missing)
  - Installs Python dependencies
  - Sets up a `.env` file
  - Exports environment variables
  - Downloads the `publisher` and `bridge` Protobuf files. (via `make publisher-proto` and `make bridge-proto` respectively)
  - Compiles gRPC protos (via `make grpc-compile`)

- `quick-start`:
  - Launches the REST server, IMAP Listener, and the FTP Server.

> [!WARNING]
>
> This setup is for development only. Do not use in production.

## System Requirements

- **Database:** MySQL (≥ 8.0.28), MariaDB, or SQLite
- **Python:** ≥ 3.8.10
- **Virtual Environments:** Python venv

### Ubuntu Dependencies

```bash
sudo apt update
sudo apt install python3-dev libmysqlclient-dev apache2 apache2-dev make libapache2-mod-wsgi-py3
```

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/smswithoutborders/RelaySMS-Gateway-Server.git
   cd RelaySMS-Gateway-Server
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Compile gRPC protos:**

   ```bash
   make grpc-compile
   ```

## Building and Running with Docker

#### Build the Docker Image

```bash
docker build -t relaysms-gateway-server .
```

#### Run the Container

> [!TIP]
>
> **For long-term development, you may want to run the container in detached mode (`-d`) and view logs with:**
>
> ```bash
> docker logs -f <container_id_or_name>
> ```

```bash
docker run --rm \
  --env-file .env \
  -p 5000:5000 -p 5001:5001 \
  -p 2222:2222 -p 60000-65000:60000-65000 \
  -v $(pwd)/ftp_file_store:/gateway_server/ftp_file_store \
  relaysms-gateway-server
```

> [!TIP]
>
> - To run in detached mode:
>   ```bash
>   docker run -d \
>     --name relaysms-gateway-server \
>     --env-file .env \
>     -p 5000:5000 -p 5001:5001 \
>     -p 2222:2222 -p 60000-65000:60000-65000 \
>     -v $(pwd)/ftp_file_store:/gateway_server/ftp_file_store \
>     relaysms-gateway-server
>   ```
>   Then view logs with:
>   ```bash
>   docker logs -f relaysms-gateway-server
>   ```

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

### Bridge gRPC

- `BRIDGE_GRPC_HOST`: Bridge gRPC server host (default: `127.0.0.1`)
- `BRIDGE_GRPC_PORT`: Bridge gRPC server port (default: `10000`)

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
- `FTP_DIRECTORY`: FTP directory path (default: `ftp_file_store`)

### Security

- `SMTP_ALLOWED_EMAIL_ADDRESSES`: Allowed email addresses for SMTP
- `DISABLE_BRIDGE_PAYLOADS_OVER_HTTP`: Disable bridge payloads over HTTP (default: `false`)

### Logging

- `LOG_LEVEL`: Logging level (default: `info`)

## References

- REST API Resources:
  - [API V3](docs/api_v3.md)
- [Gateway Client CLI](docs/gateway_clients_cli.md)

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-branch`
3. Commit your changes
4. Push to your branch
5. Open a pull request

## License

Licensed under the GNU General Public License (GPL). See [LICENSE](LICENSE) for details.
