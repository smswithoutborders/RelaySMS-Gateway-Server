FROM python:3.14.1-slim AS base

WORKDIR /gateway_server

RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
	--mount=type=cache,sharing=locked,target=/var/lib/apt \
	apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	apache2 \
	apache2-dev \
	default-libmysqlclient-dev \
	supervisor \
	git \
	vim \
	curl \
	pkg-config && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,sharing=locked,target=/root/.cache/pip \
	pip install --disable-pip-version-check --quiet --no-cache-dir -r requirements.txt

COPY . .

RUN make grpc-compile

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

ENV MODE=production
CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
