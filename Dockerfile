FROM python:3.13.3-slim AS base

WORKDIR /gateway_server

RUN apt-get update && \
	apt-get install -y --no-install-recommends \
	build-essential \
	apache2 \
	apache2-dev \
	default-libmysqlclient-dev \
	supervisor \
	git \
	curl \
	pkg-config && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
	pip install --disable-pip-version-check --quiet --no-cache-dir -r requirements.txt

COPY . .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
