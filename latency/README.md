# Preparation

Extract MaxMindDB and link to the database file

    cd data
    tar xf GeoLite2-City.tar.gz
    ln -vs GeoLite2-City_20180102/GeoLite2-City.mmdb

# List of probes

**`cache/all-probes.json`**

After running `01-test-reachability.py` for the first time, this file will be
created.  You probably don't want this to change while you're gathering data.
So make sure all scripts that reference it are configured with a
`--probe-list-age` that's functionally infinite.

# `01-test-reachability.py`

The API key for this script needs the following permissions.

- Get information about your credits
- Schedule a new measurement
- List your measurements

When stopping `01-test-reachability.py`, **only hit ctrl-c once**. The script
will wait for existing measurements to finish, create the queued measurements,
and wait for them to finish too. It could take ~20 minutes, but it will stop.

## Notable arguments

**`--measurements-file`**
Where to dump the reachability results. This is the output of the script.

**`--src-probe`**
The probe ID of a RIPE Atlas probe. Ideally it's well-connected to the
Internet, as it will be the one that tries pinging all the other probes and
determining if they are reachable.

**`--api`**
A RIPE Atlas API key, as describe above.

**`--threads`**
Increasing this increases the number of parallel measurements you create and
for which you wait on results. One thread is stupid and will take you forever.
Twenty threads works fine as of April 2020. Threads mostly sleep, so many
threads doesn't peg your CPU. Too many threads and RIPE's API gateway will
start returning errors.

**`--results-per-day`**
RIPE's limit on how many results you can get per day is the main limiting
factor for this script. As of April 2020 it was 100,000 for Matt.`You can find
it [here](https://atlas.ripe.net/atlas/user/) when logged in to RIPE Atlas. Set
this to near the limit.

**`--test-name-prefix`**
should be unique for the RIPE Atlas account if you don't want to pull in old
results. The prefix is used to identity measurements that were done as part of
this ... measurement collection. The default value is what Matt used in his
2018 measurements.

## Cost
Assuming ~6000 online probes with an IPv4 address and a city (the latter is
according to MaxMind), and assuming 6 credits per ping measurement: **36,000
credits**. 6000 is accurate as of April 2020, as is 2 credits per ICMP ping (3
pings in a measurement, thus 6 credits for a measurement).

## Runtime
A week? A runtime estimate is logged every 5 minutes. You can cut the time in
half by splitting the work across two different RIPE Atlas users. Figure out a
way to split all-probes.json in half and run the script twice with different
API keys. And then combine results back together. Good luck.
