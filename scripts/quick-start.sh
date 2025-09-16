#!/bin/bash

trap "kill 0" EXIT

make start-rest-api &
make start-imap-listener &
make start-ftp-server &

wait
