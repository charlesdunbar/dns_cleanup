# dns_cleanup
Python script used to find stale dynamic DNS records

This script runs through a domain, finds any records that have both an A and TXT record, which indicates they were created with dynamic DNS, attempts to pings them twice, and prints any host that doesn't respond to ping into a file that can be passed into nsupdate.

## Use

```
usage: dns_cleanup.py [-h] [-f] [-v] [-w] zone dns_server

positional arguments:
  zone              the zone to purge stale ddns records
  dns_server        DNS server to use to resolve a domain

optional arguments:
  -h, --help        show this help message and exit
  -f , --filename   file output destination - default is /tmp/{zone}.ns
  -v, --verbose     increase verbosity
  -w , --workers    number of worker threads used in pinging (default 4)
```