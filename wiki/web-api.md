# Web API

<h2>Table of contents</h2>

- [What is a web API](#what-is-a-web-api)
- [Endpoint](#endpoint)
- [Base URL](#base-url)
- [API key](#api-key)
  - [`<api-key>` placeholder](#api-key-placeholder)

## What is a web API

A web API is an [API](./api.md#what-is-an-api) that a [web server](./web-infrastructure.md#web-server) exposes over a [protocol](./communication-protocol.md#what-is-a-protocol). It accepts requests from [web clients](./web-infrastructure.md#web-client) and returns structured responses.

Docs:

- [An introduction to APIs: A comprehensive guide](https://zapier.com/blog/api/)
- [Introduction to web APIs](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Client-side_APIs/Introduction)

## Endpoint

An endpoint is a specific entry point of a [web API](#what-is-a-web-api), identified by a path (`/status`, `/items`, ...).

In a [`REST` API](./rest-api.md#what-is-a-rest-api), the [`HTTP` method](./http.md#http-request-method) is also part of the identity — `GET /status` and `POST /status` are different endpoints.

## Base URL

The base [URL](./computer-networks.md#url) is the common prefix shared by all [endpoints](#endpoint) of a [web API](#what-is-a-web-api). It identifies the server and, optionally, a path prefix such as a version segment.

To form a complete request URL, append an endpoint path to the base URL:

| Part     | Example                            |
| -------- | ---------------------------------- |
| Base URL | `https://api.example.com/v1`       |
| Endpoint | `/items`                           |
| Full URL | `https://api.example.com/v1/items` |

## API key

An API key is a secret value used to [authenticate](./http-auth.md#http-authentication) a client making requests to a [web API](#what-is-a-web-api). The server rejects requests with a missing or invalid key with [`401 Unauthorized`](./http.md#401-unauthorized).

The API key is sent in the `Authorization` header of every request:

```http
Authorization: Bearer <api-key>
```

### `<api-key>` placeholder

The value of the [API key](#api-key) (without `<` and `>`) that you use to authenticate in the [API](#what-is-a-web-api).
