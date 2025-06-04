# API v3 Documentation

## Table of Contents

- [Base URL](#base-url)
- [Security Headers](#security-headers)
- [Endpoints](#endpoints)
  - [Get Gateway Clients](#get-gateway-clients)
  - [Get Tests for a Gateway Client](#get-tests-for-a-gateway-client)
  - [Get All Countries](#get-all-countries)
  - [Get Operators for a Country](#get-operators-for-a-country)

## Base URL

All endpoints in this API have the base URL: `/v3`

### Security Headers

All responses from this API include the following security headers:

- `Strict-Transport-Security`: Ensures that browsers will only connect to the
  server over HTTPS.
- `X-Content-Type-Options`: Prevents browsers from MIME-sniffing a response away
  from the declared content type.
- `Content-Security-Policy`: Helps prevent XSS attacks by restricting the
  sources of content that can be loaded on a web page.
- `Referrer-Policy`: Specifies how much referrer information should be included
  with requests.
- `Cache-Control`: Directs caches not to store the response.
- `Permissions-Policy`: Defines the permissions the site requires to function
  correctly.

## Endpoints

### Get Gateway Clients

```http
GET /v3/clients?country=cameroon&operator=operator_name&protocols=https,smtp,ftp&last_published_date=2024-05-27:00:00Z&per_page=20&page=2
```

#### Description

Get gateway clients with optional filters.

#### Parameters

- `country` (optional): Filter by country.
- `operator` (optional): Filter by operator.
- `protocols` (optional): Filter by protocols.
- `last_published_date` (optional): Filter by last published date. Format:
  YYYY-MM-DD
- `page` (optional): Page number for pagination (default: 1).
- `per_page` (optional): Number of results per page (default: 10).

#### Response

```json
[
  {
    "country": "Cameroon",
    "last_published_date": 1714846064,
    "msisdn": "+xxxxxxxxx",
    "operator": "OPERATOR",
    "operator_code": "xxxxxx",
    "protocols": ["https", "smtp", "ftp"],
    "reliability": "0.00"
  }
]
```

> [!NOTE]
>
> - `last_published_date` field is in
>   [unix time](https://en.wikipedia.org/wiki/Unix_time).
> - `reliability` field represents the reliability of the gateway client as a
>   percentage.

#### Errors

- `400 Bad Request`: If the request is malformed.
- `500 Internal Server Error`: If an unexpected error occurs.

#### Additional Headers

- `X-Total-Count`: Total number of records.
- `X-Page`: Current page number.
- `X-Per-Page`: Number of records per page.
- `Link`: Provides links for pagination. Refer to GitHub's
  [comprehensive documentation](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api?apiVersion=2022-11-28#using-link-headers)
  on how to use link headers.

### Get Tests for a Gateway Client

```http
GET /v3/clients/<msisdn>/tests?per_page=20&page=2
```

#### Description

Get reliability tests for a specific gateway client with optional filters.

#### Parameters

- `page` (optional): Page number for pagination (default: 1).
- `per_page` (optional): Number of results per page (default: 10).

#### Response

```json
{
  "data": [
    {
      "id": 11,
      "msisdn": "+xxxxxxxxx",
      "sms_received_time": 1747691895,
      "sms_routed_time": 1747691895,
      "sms_sent_time": 1747691895,
      "start_time": 1747691894,
      "status": "success"
    },
    {
      "id": 10,
      "msisdn": "+xxxxxxxxx",
      "sms_received_time": 1747691894,
      "sms_routed_time": 1747691894,
      "sms_sent_time": 1747691894,
      "start_time": 1747691893,
      "status": "success"
    }
    // ...more test objects...
  ],
  "total_failed": "1",
  "total_records": 11,
  "total_success": "10"
}
```

> [!NOTE]
>
> - `sms_received_time`, `sms_routed_time`, `sms_sent_time`, and `start_time`
>   fields are in [unix time](https://en.wikipedia.org/wiki/Unix_time).
> - `status` field for the tests has two values: `"success"` or `"timedout"`.

#### Errors

- `400 Bad Request`: If the request is malformed.
- `404 Not Found`: If the requested resource is not found.
- `500 Internal Server Error`: If an unexpected error occurs.

#### Additional Headers

- `X-Total-Count`: Total number of records.
- `X-Page`: Current page number.
- `X-Per-Page`: Number of records per page.
- `Link`: Provides links for pagination. Refer to GitHub's
  [comprehensive documentation](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api?apiVersion=2022-11-28#using-link-headers)
  on how to use link headers.

### Get All Countries

```http
GET /v3/clients/countries
```

#### Description

Get all countries for gateway clients.

#### Response

```json
["Cameroon", "Example Country"]
```

#### Errors

- `500 Internal Server Error`: If an unexpected error occurs.

### Get Operators for a Country

```http
GET /v3/clients/<string:country>/operators
```

#### Description

Get all operators for a specific country.

#### Parameters

- `country`: Country name.

#### Response

```json
["Operator A", "Operator B"]
```

#### Errors

- `400 Bad Request`: If the country parameter is missing.
- `500 Internal Server Error`: If an unexpected error occurs.

### Publish Payload

```http
POST /v3/publish
```

#### Description

Publishes content payload to either the **bridge server** or directly to the **publisher**, depending on the content of the payload.

#### Request Body

```json
{
  "text": "base64_encoded_payload",
  "MSISDN": "+237123456789"
}
```

- **text**: The Base64-encoded payload to be published.

  - If the first byte of the decoded payload is `0`, the system will treat it as a **bridge server** payload. The remaining bytes (after the first byte) will be forwarded to the bridge server.

  ```python
  publish_payload = bytes([0]) + b"encrypted content"
  base64_encoded_payload = base64.b64encode(publish_payload).decode("utf-8")
  ```

  - If the first byte is not `0`, the system will treat it as a regular payload and send the entire payload directly to the **publisher**.

- **MSISDN** or **address**: Required field specifying the sender's phone number.

#### Response

```json
{
  "publisher_response": "response message from publisher or bridge"
}
```

- **publisher_response**: Returns the response message based on the type of publishing (bridge server or publisher).

#### Errors

- `400 Bad Request`: If the request is malformed.
- `500 Internal Server Error`: If an unexpected error occurs.
