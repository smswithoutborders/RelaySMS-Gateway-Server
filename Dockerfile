FROM python:3.13.0-slim

RUN apt-get update && \
	apt-get install -y --no-install-recommends \
	build-essential \
	apache2 \
	apache2-dev \
	python3-dev \
	default-libmysqlclient-dev \
	supervisor \
	curl \
	rm -rf /var/lib/apt/lists/*

WORKDIR /

COPY . .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN pip install -U --quiet --no-cache-dir pip setuptools && \
	pip install --quiet --no-cache-dir --force-reinstall -r requirements.txt 

ENV MODE=production
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
