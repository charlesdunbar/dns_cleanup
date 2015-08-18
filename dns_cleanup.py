#!/usr/bin/env python

# Script used to check for stale DNS records. We had a bug in our isc-dhcp-server that caused
# dynamic dns entries to not be removed when the lease expired.  This script checks for records
# with both an A and TXT record, pings them twice, and outputs the hosts that don't respond into
# files with 1000 records per file (500 A, 500 TXT).  This allows for easy nsupdating to remove
# any records
#
# Author: Charles Dunbar

import argparse
import dns.query
import dns.zone
import subprocess
import threading

# Parse args
parser = argparse.ArgumentParser()
parser.add_argument("zone", help="the zone to purge stale ddns records", type=str)
parser.add_argument("dns_server",  help="DNS server to use to resolve a domain", type=str)
parser.add_argument("-f", "--filename",  help="file output destination - default is /tmp/{zone}.ns", metavar='')
parser.add_argument("-v", "--verbose",  help="increase verbosity", action="store_true")
parser.add_argument("-w", "--workers",  help="number of worker threads used in pinging (default 4)", default=4, type=int, metavar='')
args = parser.parse_args()

# Set default file location
if args.filename is None: args.filename = "/tmp/{0}.ns".format(args.zone)

suspect_list = []
dead_list = []

# Pinger class found from http://blog.boa.nu/2012/10/python-threading-example-creating-pingerpy.html
# Slight modifications used to match what I'm doing
class Pinger(object):
    hosts = [] # List of all hosts

    # Lock object to keep track the threads in loops, where it can potentially be race conditions.
    lock = threading.Lock()

    def ping(self, host):
        # Use the system ping command with count of 2 and wait time of 1.
	p = subprocess.Popen(["ping", host[0].to_text() + "." + args.zone, "-c", "2", "-W", "1"], stdout=subprocess.PIPE)
	output = p.communicate()[0]
	if args.verbose: print output
	if p.returncode != 0:
	    if args.verbose: print "Host appears down, adding to list to be removed"
	    dead_list.append(host)
	else:
	    if args.verbose: print "Host appears up"

    def pop_queue(self):
        host = None

        self.lock.acquire() # Grab or wait+grab the lock.

        if self.hosts:
            host = self.hosts.pop()

        self.lock.release() # Release the lock, so another thread could grab it.

        return host 

    def dequeue(self):
        while True:
            host = self.pop_queue()

            if not host:
                return None

            self.ping(host) 

    def start(self):
        threads = []

        for i in range(self.thread_count):
            # Create self.thread_count number of threads that together will
            # cooperate removing every ip in the list. Each thread will do the
            # job as fast as it can.
            t = threading.Thread(target=self.dequeue)
            t.start()
            threads.append(t)

        # Wait until all the threads are done. .join() is blocking.
        [ t.join() for t in threads ]

def get_suspects():
    try:
	if args.verbose: print "Transfering {0} from DNS server 10.240.0.10\n".format(args.zone)
	zone = dns.zone.from_xfr(dns.query.xfr(args.dns_server, args.zone))
	for i in zone.nodes.items():
	    # If a record has 2 types, check if one's A and one is TXT
	    # Append to list if they are
	    if len(i[1].rdatasets) == 2:
		if i[1].rdatasets[0].rdtype == dns.rdatatype.TXT and i[1].rdatasets[1].rdtype == dns.rdatatype.A or \
		    i[1].rdatasets[1].rdtype == dns.rdatatype.TXT and i[1].rdatasets[0].rdtype == dns.rdatatype.A:
		    suspect_list.append(i)
    except Exception as e:
	print e

def ping_suspects():
    # Add whitespace
    if args.verbose: print ""
    ping = Pinger()
    ping.thread_count = args.workers
    ping.hosts = suspect_list
    ping.start()


def save_to_file(filename):
    try:	
	open_file = str(filename) + ".0"
	f = open(open_file, 'wb')
	for i, record in enumerate(dead_list):
	    if not i % 500: # Only want 500 host entries per file, 1000 lines per file
		f.write("send\n")
		f.close()
		open_file = str(filename) + ".{0}".format(i/500)
		f = open(open_file, 'wb')
	    for x in record[1].rdatasets:
		f.write("update delete {0}.{1} {2} {3} {4}\n".format(record[0].to_text(), args.zone, str(x.ttl), dns.rdatatype.to_text(x.rdtype), x.items[0].to_text()))
    finally:
	f.write("send\n")
	f.close()

if __name__ == "__main__":
    print "Finding records in zone {0} with both an A and TXT record".format(args.zone)
    get_suspects()
    if args.verbose:
	print "The {0} suspected records with both A and TXT records are:".format(len(suspect_list))
	for i in suspect_list:
	    print i[0].to_text()
    print "{0} suspected records".format(len(suspect_list))
    if len(suspect_list) > 0:
	ping_suspects()
    if args.verbose:
	print "The {0} records that don't reply to ping are:".format(len(dead_list))
	for i in dead_list:
	    print i[0].to_text() 
    print "{0} dead records found".format(len(dead_list))
    if len(dead_list) > 0:
	save_to_file(args.filename)
	print "Wrote file to {0} - check the output and run nsupdate on {0}.*`".format(args.filename)
    
