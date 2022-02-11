# SMSWithoutBorders Gateway Server
### Requirements
- python3
- RabbitMQ


### Features
- Message broker server for [Gateway-Client]() (_see [SMSWithoutBorders-OpenAPI]()_ )
- [SMSWithoutBorders-App]() [synchronization](synchronization) for communication with [Publisher]()
	> This should should be hosted in the same place as [Publisher](), because Publisher is not _directly_ exposed to the web.
- Forwards publishing request from [Gateway-Client]() to [Publisher]()
- Authenticates [Gateway-Client's]() request to join [Publisher]()

<a name="synchronization" />
#### Synchronization
Synchronization is required to enable the users acquire security keys, platforms and available gateways.

_The process of synchronization_
1. Begin by requesting for a new session. This comes in the form of a url for an websocket which will begin
streaming synchronization urls to the socket clients. The frequency of change of the synchronization urls depends
on the configuration settings `[sync] session_sleep_timeout` (defaults = 15 seconds). \
The total number of changes per frequency can be changed in `[sync] session_change_limit` (defaults = 3 times)

`POST /<api-version>/sync/users/<user-id>`

This returns a string url, which can be connected to by websocket clients.

<url>, `200` session created

'', `500` some error occured, check debug logs

2. Once a sync url is connected, the websocket sends an acknowlegment `ACK - 200` and the socket connection is closed.
The user begins authentictating themselves and adding their security policies to their record on the server.

<a name="testing" />
#### Testing
Testing [Users model](gateway_server/users/Users.py)
```bash
python -m unittest gateway_server/test/UTestUsers.py
```

### Installation
```bash
https://github.com/smswithoutborders/SMSWithoutBorders-Gateway-Server.git
git submodule update --force --recursive --init --remote
cd SMSWithoutBorders-Gateway-Server 
python3 -m virtualenv venv
. venv/bin/activate
pip3 install -r requirements.txt
```

### Configuration
- Copy the config files and edit the
```
cp .configs/example.config.ini .configs/config.ini
```
