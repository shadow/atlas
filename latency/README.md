Extract MaxMindDB and link to the database file

    cd data
    tar xf GeoLite2-City.tar.gz
    ln -vs GeoLite2-City_20180102/GeoLite2-City.mmdb

# List of probes

**`cache/all-probes.json`**

You probably don't want this to change while you're gathering data. So make
sure all scripts that reference it are configured with a `--probe-list-age`
that's functionally infinite.

# `01-test-reachability.py`

The API key for this script needs the following permissions.

- Get information about your credits
- Schedule a new measurement
- List your measurements

When stopping `01-test-reachability.py`, **only hit ctrl-c once**. The script
will wait for existing measurements to finish, create the queued measurements,
and wait for them to finish too. It could take ~20 minutes, but it will stop.

The `--test-name-prefix` should be unique for the RIPE Atlas account if you
don't want to pull in old results. The prefix is used to identity measurements
that were done as part of this ... measurement collection. The default value is
what Matt used in his 2018 measurements.

## Cost
Assuming ~6000 probes and 6 credits per ping measurement: 36,000 credits.
