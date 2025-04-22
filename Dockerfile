FROM python:3.13.3-slim

RUN apt-get update && \
	apt-get install -y --no-install-recommends \
	build-essential \
	apache2 \
	apache2-dev \
	python3-dev \
	default-libmysqlclient-dev \
	supervisor \
	git \
	pkg-config \
	curl && \
	rm -rf /var/lib/apt/lists/*

WORKDIR /

COPY . .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN pip install --disable-pip-version-check --quiet --no-cache-dir --force-reinstall -r requirements.txt 

ENV MODE=production
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
