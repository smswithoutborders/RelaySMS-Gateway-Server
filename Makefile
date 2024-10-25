python=python3
PROTO_DIR=protos/v1

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

setup: grpc-compile start-rest-api

publisher-proto: 
	@rm -f "$(PROTO_DIR)/publisher.proto"
	@$(MAKE) PROTO_URL=https://raw.githubusercontent.com/smswithoutborders/SMSWithoutBorders-Publisher/main/protos/v1/publisher.proto \
	$(PROTO_DIR)/publisher.proto

grpc-compile: publisher-proto
	$(call log_message,INFO - Compiling gRPC protos ...)
	@$(python) -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=. \
		--pyi_out=. \
		--grpc_python_out=. \
		$(PROTO_DIR)/*.proto
	$(call log_message,INFO - gRPC Compilation complete!)
	
start-rest-api:
	@(\
		echo "[$(shell date +'%Y-%m-%d %H:%M:%S')] - INFO - Starting REST API ..." && \
		mod_wsgi-express start-server wsgi_script.py \
			--user www-data \
			--group www-data \
			--port '${PORT}' \
			--ssl-certificate-file '${SSL_CERTIFICATE}' \
			--ssl-certificate-key-file '${SSL_KEY}' \
			--ssl-certificate-chain-file '${SSL_PEM}' \
			--https-only \
			--server-name '${HOST}' \
			--https-port '${SSL_PORT}' \
			--log-to-terminal; \
	)
