## Files of interest:

...to be updated...

## Installation

*   git clone https://github.com/wing-aviation/InterUSS-Platform.git
*   sudo apt install python-virtualenv python-pip
*   virtualenv USSenv
*   cd USSenv
*   . bin/activate
*   pip install flask psycopg2 pytest python-dateutil pyopenssl shapely
*   pip install requests pyjwt cryptography djangorestframework pytz
*   ln -sf ../InterUSS-Platform/datanode/src ./src
*   export INTERUSS_PUBLIC_KEY=(The public KEY for decoding JWTs)
*   python src/storage_api.py --help
    *   For example: python src/storage_api.py -c
        "host=localhost port=26257 dbname=defaultdb user=root password=" -s 0.0.0.0 -p 8121 -t
        test-instance  -v

See also the configurations described in ../docker.
