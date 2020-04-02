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
`--probe-list-age` that's functionally infinite. It would be smart to back this
file up once it's generated.

# API key

The API key for these script needs the following permissions.

- Get information about your credits
- Schedule a new measurement
- List your measurements

Create an API key [here](https://atlas.ripe.net/keys/).

# `01-test-reachability.py`

This is the first primary latency measurements script.

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

# `02-pick-best-by-city.py`

Once `01-test-reachability.py` is done, run this to parse the list of all
probes, `cache/all-probes.json`, into a list of just the selected probes at
`data/selected-probes.json`. This also generates the file
`cache/all-pairs.txt` which is the list of measurements needed to do the `n^2`
pairwise pings between the `n` selected probes.

Backup the output files of this script.

# `03-all-pairs-ping.py`

This is the other primary script for latency measurements. Expect this to take
over a week to run.

It's input is the plaintext line-based `cache/all-pairs.txt`. If you have
access to multiple RIPE Atlas accounts, shuffle the lines in this file, split
it into multiple pieces, and run one instance of this script for each input
piece. Use different output files too, of course.

It's output is the plaintext line-based `cache/all-pairs-measurements.txt`.
It's very similar to the input file format, but with the measurement ID numbers
on the lines as well.

This script doesn't fetch measurement results itself, but it does wait for the
measurements to be done before starting new ones.

20 threads should be plenty to keep enough measurements going in parallel that
you spend the maximum amount of credits every day.

There are lots of sleeps in the main loop.

- Sleep for 15 minutes if we cannot create any measurements right now. The
  script bumps into the 24hr spending limit. We could be waiting for quite a
  while.
- Sleep for 60 seconds for every new measurement. This helps spread them out
  over the day. There's not much of a point in spending all our daily credit
  allowance in 1 hour. Slow down our hammering of API usage. Spread out our
  spending so we're less bursty and can stay closer to the limit for longer.

# `04-fetch-all-pairs-results.py`

Run this after `03-al-pairs-ping.py`. Periodically while 03 is running is fine
too. This fetches the results from RIPE and stores them all in a file.

The size of the output file `cache/all-pairs-results.json` will get quite
large, thus the script only rewrites the file periodically (controlled with
`--write-results-every`, default to every 5 fetched results). Yes it would be
better if this wrote one result per line and simply appended to this file, but
that's not how I wrote it 2 years ago, sorry.

# `05-generate-csv.py`

This is the final script. Generates the CSV to be used for generating the
network topology.
