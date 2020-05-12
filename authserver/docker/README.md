# InterUSS Platform auth server Docker deployment

## Introduction

The contents of this folder enable the bring-up of a docker-compose system to
host an InterUSS Platform auth server in a single command.

## Contents

### Dockerfile_authserver

This Dockerfile builds an image containing a simple auth server serving via
HTTP. It is insecure to use this auth server by itself because users
authenticate with Basic authentication, so passwords are sent in the clear
without an HTTPS wrapper.

### private.pem & public.pem

This is an example keypair generated via the method described in "Access token key pair" below for the purpose of expediting the ability to run a test instance.

### roster.txt

This is an example roster of users (and passwords) for the purpose of expediting the ability to run and use a test instance.

## Running an auth server

### Resources

Before starting an auth server, a few resources must be generated.

#### Access token key pair

The auth server relies on encoding access tokens with a private key and publishing a public key with
which others may validate them.  To generate this key pair, create a new folder and, in it:

```shell
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -outform PEM -pubout -out public.pem
```

Be careful never to share private.pem.

#### Roster

The core of the auth server is translating user credentials into access tokens.  A roster defines
the set of users, their passwords, and their respective scopes.  Create `roster.txt` in the same
folder as the key pair above and populate it with one line per user.  Each line should consist of
the user's username, their hashed password, and the scopes they are to be granted, each of those
three fields separated by commas (and be careful to eliminate whitespace).  The scopes should be
separated by spaces.  The hashed password is the SHA256 hash of
`InterUSS Project USERNAME PASSWORD InterUSS Project`.  So, if user `example.com` had password `example`, their hashed
password would be SHA256(InterUSS Project example.com example InterUSS Project), which begins 32a43c.  To compute the
SHA256 hash on a Linux command line:

```shell
echo -n "InterUSS Project example.com example InterUSS Project" | openssl dgst -sha256
```

Or, use an online SHA256 generator like https://www.xorbin.com/tools/sha256-hash-calculator, but
this is less secure because the website may gain access to the password.

When enrolling a user, it is best to have them choose their password and only send you their hashed
password so the password itself is never stored in email servers.

The example roster in this repository contains the following users:

STRATEGIC_COORDINATION = 'utm.strategic_coordination'
CONSTRAINT_CONSUMPTION = 'utm.constraint_consumption'
CONSTRAINT_MANAGEMENT = 'utm.constraint_management'

| username    | password | utm.strategic_coordination | utm.constraint_consumption | utm.constraint_management |
|-------------|----------|----------------------------|----------------------------|---------------------------|
| uss1        | uss1     | X                          | X                          | X                         |
| uss2        | uss2     | X                          | X                          | X                         |
| uss3        | uss3     | X                          | X                          | X                         |
| example.com | example  | X                          | X                          | X                         |
| planner1    | planner1 | X                          |                            |                           |
| planner2    | planner2 | X                          |                            |                           |
| planner3    | planner3 | X                          |                            |                           |
| info_uss    | info     |                            | X                          |                           |
| safety_uss  | safety   |                            |                            | X                         |

### Running

To run a fully-functional InterUSS Platform auth server from the folder containing the resources
above:

```shell
export INTERUSS_AUTH_PATH=`pwd`
export SSL_CERT_PATH=`pwd`/certs
export SSL_KEY_PATH=`pwd`/private
export INTERUSS_AUTH_ISSUER=yourdomain.com
cd /path/to/this/folder
docker-compose -p authserver up
```

To verify operation, navigate a browser to https://localhost:8121/status

To make sure you have the latest versions, first run:

```shell
docker pull interussplatform/auth_server
docker pull interussplatform/auth_reverse_proxy
```
