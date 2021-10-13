# Diagnostic tool to monitor DSS and USS interactions

## Description
This diagnostic tool monitors UTM traffic in a specified area.  This includes,
when requested, remote ID Identification Service Areas and Subscriptions, and
strategic deconfliction Operations, Constraints, and Subscriptions.  This tool
records data in a way not allowed in a standards-compliant production system, so
should not be run on a production system.

## Building the image
From the [`root folder of this repo`](../..) folder, first build the tracer
image:

```shell script
docker build \
    -f monitoring/tracer/Dockerfile \
    -t interuss/dss/tracer \
    --build-arg version=`scripts/git/commit.sh` \
    monitoring
```

## Polling mode
Polling mode periodically queries the DSS regarding the objects of interest and
notes when they appear, change, or disappear.  The primary advantage to this
mode is that it operates as a client only and does not require routing to
support an externally-accessible server.  One disadvantage is that fast changes
are not detected.  For instance, if an ISA was added and then deleted all within
a single polling period, this tool would not create an record of that ISA.

### Invocation
```shell script
docker run --name tracer_run --rm -v `pwd`/logs:/logs interuss/dss/tracer \
    python python tracer_poll.py \
    --auth=<SPEC> \
    --dss=https://example.com \
    --area=34.1234,-123.4567,34.4567,-123.1234 \
    --output-folder=/logs \
    --rid-isa-poll-interval=15 \
    --scd-operation-poll-interval=15 \
    --scd-constraint-poll-interval=15
```

The auth SPEC defines how to obtain access tokens to access the DSS instances
and USSs in the network. See
[the auth spec documentation](../monitorlib/README.md#Auth_specs) for examples
and more information.

## Subscribe mode
Subscribe mode emplaces Subscriptions in the DSS and listens for incoming
notifications of changes from other USSs.  The two primary advantages to this
mode are that no ongoing polling is necessary and details of Entities are
delivered automatically -- the only outgoing requests happen at initialization
and shutdown.  The disadvantages include requiring an external route to this,
probably with TLS unless the TLS check is disabled in the DSS, and that
information logging is dependent on USSs behaving correctly and sending
notifications upon DSS prompting.

### Invocation
Make a copy of [`run_subscribe.sh`](run_subscribe.sh) and edit the arguments as
appropriate.  Then simply run your copy of that script (`./run_subscribe.sh`).
To stop this container gracefully (so that Subscriptions are removed):
`docker container kill --signal=INT tracer_subscribe`

### External route
One important argument in subscribe mode is `--base-url`.  This should be the
URL at which the tracer container can be reached externally.  Note that this URL
will probably need to use https (to satisfy DSS validation), but the tracer
container only serves via http.  This means a user will need to provide their
own TLS termination for the external endpoint and forward traffic to the tracer
container in order to use tracer in subscribe mode.

#### Example setup


### Log viewer
While tracer is running in subscribe mode, visit /logs relative to the base URL
(e.g., https://example.com/logs) to see a list of log entries recorded by tracer
while the current session has been running.

## Full deployment

One way to fully deploy a tracer instance is as follows:

1. Set up infrastructure
    1. Create cloud VM (or physical machine exposed externally) with Debian or
       similar distribution installed
    1. Make sure ports 80 and 443 are open to the VM (not blocked at firewall)
    1. Reserve a static IP address for the VM
    1. Add a DNS entry pointing your FQDN for your tracer instance to your VM's
       static IP address
1. Set up tools on VM
    1. Install git (`sudo apt-get install git`)
    1. [Install Docker](https://docs.docker.com/engine/install/debian/), and possibly [manage docker as a non-root user](https://docs.docker.com/engine/install/linux-postinstall/)
    1. [Install docker-compose](https://docs.docker.com/compose/install/)
1. Set up TLS termination
    1. Check out the reverse-proxy repository (`git clone https://github.com/BenjaminPelletier/reverse-proxy`)
    1. Build reverse proxy image (`docker image build -f Dockerfile -t benpelletier/reverse_proxy .`)
    1. Create reverse proxy configuration
        1. `cp reverse-proxy/nginx/conf/reverse_proxy.conf.example reverse-proxy/nginx/conf/reverse_proxy.conf`
        1. `nano reverse-proxy/nginx/conf/reverse_proxy.conf`
            1. Change `internal_service_1` to `tracer` (in both `upstream` definition and `server` block)
            1. Change the upstream `server` for `tracer` to `tracer_subscribe:5000`
            1. Change `server_name` as appropriate
            1. Delete `internal_service_2` and its corresponding `server` block
            1. Save and exit
    1. Edit startup command (`nano reverse-proxy/reverse_proxy.sh`) and insert the line `  --network localvm \` just after the `docker run \` line, then save and exit
1. Set up tracer
    1. Check out this repository (`git clone https://github.com/interuss/dss`)
    1. Build tracer image:
       ```
       docker build \
           -f dss/monitoring/tracer/Dockerfile \
           -t interuss/dss/tracer \
           --build-arg version=`cd dss && scripts/git/commit.sh` \
           dss/monitoring
       ```
    1. Create a logs folder (`mkdir logs`)
    1. Create `tracer_poll.sh` and `tracer_subscribe.sh` scripts (see below) and
       mark them as executable (`chmod +x tracer_poll.sh`,
       `chmod +x tracer_subscribe.sh`)
    1. Create a network for tracer_subscribe and reverse proxy to share (`docker network create localvm`)
1. Bring up system
    1. Bring up tracer polling (`./tracer_poll.sh`)
        1. Verify no errors: `docker container logs tracer_poll`
    1. Bring up tracer subscription (`./tracer_subscribe.sh`)
        1. Verify no errors: `docker container logs tracer_subscribe`
    1. Bring up reverse proxy (`cd reverse-proxy` then `./reverse_proxy.sh`)
        1. Verify "ready for start up": `docker container logs reverseproxy`
    1. Enable TLS (`./get_first_certs.sh`)
        1. When prompted, select "2: Redirect"

### tracer_poll.sh

This script should start an instance of tracer in polling mode; replace all of
the values below with values appropriate to your use case.

```shell
#!/usr/bin/env bash

docker container rm -f tracer_poll

docker run --name tracer_poll --rm \
    -d \
    -v `pwd`/logs:/logs \
    interuss/dss/tracer \
    python tracer_poll.py \
    --auth="ClientIdClientSecret(https://auth.example.com/oauth/token,client_id=MYID,client_secret=MYSECRET)" \
    --dss=https://dss.example.com \
    --area=46.97,7.47,46.99,7.50 \
    --output-folder=/logs \
    --rid-isa-poll-interval=15 \
    --scd-operation-poll-interval=15 \
    --scd-constraint-poll-interval=15 \
    --trace-hours=23.995
```

### tracer_subscribe.sh

This script should start an instance of tracer in subscription mode; replace all
of the values below with values approriate to your use case.

```shell
#!/usr/bin/env bash

AUTH='--auth=ClientIdClientSecret(https://auth.example.com/oauth/token,client_id=MYID,client_secret=MYSECRET)'
DSS='--dss=https://dss.example.com'
AREA='--area=46.97,7.47,46.99,7.50'
LOGS='--output-folder=/config/logs'
BASE_URL='--base-url=https://tracer.example.com'
MONITOR='--monitor-rid --monitor-scd'
DURATION='--trace-hours=23.995'
PORT=5000

TRACER_OPTIONS="$AUTH $DSS $AREA $LOGS $BASE_URL $MONITOR $DURATION"

docker container rm -f tracer_subscribe

docker run --name tracer_subscribe \
  --rm \
  -d \
  --network="localvm" \
  -e TRACER_OPTIONS="${TRACER_OPTIONS}" \
  -p ${PORT}:5000 \
  -v `pwd`:/config \
  interuss/dss/tracer \
  gunicorn \
    --preload \
    --workers=2 \
    --bind=0.0.0.0:5000 \
    monitoring.tracer.uss_receiver:webapp
```
