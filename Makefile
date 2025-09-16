python=python3
PROTO_DIR=protos/v1
CURRENT_BRANCH=$(shell git branch --show-current)

define log_message
	@echo "[$(shell date +'%Y-%m-%d %H:%M:%S')] - $1"
endef

define download-proto
	$(call log_message,INFO - Downloading $(PROTO_URL) to $@ ...)
	@mkdir -p $(dir $@) && \
	curl -o $@ -L $(PROTO_URL)
	$(call log_message,INFO - $@ downloaded successfully!)
endef

$(PROTO_DIR)/%.proto:
	$(eval PROTO_URL := $(PROTO_URL))
	$(call download-proto)

publisher-proto: 
	@rm -f "$(PROTO_DIR)/publisher.proto"
	@$(MAKE) PROTO_URL=https://raw.githubusercontent.com/smswithoutborders/RelaySMS-Publisher/$(CURRENT_BRANCH)/protos/v1/publisher.proto \
	$(PROTO_DIR)/publisher.proto

bridge-proto: 
	@rm -f "$(PROTO_DIR)/bridge.proto"
	@$(MAKE) PROTO_URL=https://raw.githubusercontent.com/smswithoutborders/RelaySMS-Bridge-Server/$(CURRENT_BRANCH)/protos/v1/bridge.proto \
	$(PROTO_DIR)/bridge.proto

grpc-compile: publisher-proto bridge-proto
	$(call log_message,INFO - Compiling gRPC protos ...)
	@$(python) -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=. \
		--pyi_out=. \
		--grpc_python_out=. \
		$(PROTO_DIR)/*.proto
	$(call log_message,INFO - gRPC Compilation complete!)
	
start-rest-api:
	$(call log_message,[INFO] Starting REST API ...)
	@if [ "$$MODE" = "production" ]; then \
		echo "[INFO] Running in production mode with SSL"; \
		gunicorn -w 4 -b 0.0.0.0:$$SSL_PORT \
			--log-level=info \
			--access-logfile=- \
			--certfile=$$SSL_CERTIFICATE \
			--keyfile=$$SSL_KEY \
			--threads 15 \
			--timeout 30 \
			main:app; \
	else \
		echo "[INFO] Running in development mode without SSL"; \
		gunicorn -w 1 -b 0.0.0.0:$$PORT \
			--log-level=info \
			--access-logfile=- \
			--threads 3 \
			--timeout 30 \
			main:app; \
	fi
	$(call log_message,[INFO] REST API started successfully.)

start-imap-listener:
	$(call log_message,[INFO] Starting IMAP Listener ...)
	@$(python) -m src.imap_listener
	$(call log_message,[INFO] IMAP Listener started successfully.)

start-ftp-server:
	$(call log_message,[INFO] Starting FTP Server ...)
	@$(python) -m src.ftp_server
	$(call log_message,[INFO] FTP Server started successfully.)
