FROM python:3.13

RUN apt-get update && \ 
	apt-get install -y \
	build-essential \
	apache2 \
	apache2-dev \
	python3-dev \
	default-libmysqlclient-dev \
	supervisor 

WORKDIR /gateway-server

COPY . .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN pip install -U pip && \
	pip install --no-cache-dir wheel && \
	pip install --no-cache-dir --force-reinstall -r requirements.txt && \
	usermod -u 1000 www-data && \
	usermod -G root www-data

ARG PORT=$PORT
ARG HOST
ARG SSL_CERTIFICATE
ARG SSL_KEY
ARG SSL_PEM
ARG SSL_PORT

RUN mod_wsgi-express setup-server wsgi_script.py \
	--setup-only \
	--server-root /tmp/httpd \
	--error-log-name /tmp/httpd/error.log \
	--access-log-name /tmp/httpd/error.log \
	--startup-log-name /tmp/httpd/error.log \
	--user www-data \
	--group www-data \
	--port $PORT \
	--server-name ${HOST} \
	--ssl-certificate-file ${SSL_CERTIFICATE} \
	--ssl-certificate-key-file ${SSL_KEY} \
	--ssl-certificate-chain-file ${SSL_PEM} \
	--https-port ${SSL_PORT}

RUN sed -i "s/15002/$( echo $PORT )/g" apache.conf && \
	echo "Include '/gateway-server/apache.conf'" | \
	cat - /tmp/httpd/httpd.conf > /tmp/file.txt | \
	mv /tmp/file.txt /tmp/httpd/httpd.conf

ENV MODE=production
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
