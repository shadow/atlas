# `01-gen-country-codes.py`

You need to extraact GeoLite2 city data:

    cd data
    unzip GeoLite2-City-CSV_20200331.zip
    mv GeoLite2-City-CSV_20200331/GeoLite2-City-Locations-en.csv .
    rm -r GeoLite2-City-CSV_20200331/

Then you generate `country-codes.txt` like this:

    <data/GeoLite2-City-Locations-en.csv \
        ./01-gen-country-codes.py \
        >data/country-codes.txt

It won't be perfect. You'll have to do some manual editing of
`data/country-codes.txt` during a later step.

# `02-download.sh`

Run this to scrape the part of speedtest.net with the data.

Most likely speedtest.net has changed the layout of their website again. They
did between 2018 and 2020 (ugh). Have fun editing the wget commands and
figuring out where the data is on the website, if at all anymore.

# `03-parse-data.py`

We got countries setup mostly. You're going to interate on this for a bit
to get country stuff taken care of before moving on to cities.

Run this script. You'll find that ~10% of the countries aren't found in the
"global index country code data" (`data/country-codes.txt`) so you're going to
have to fix that. For example:

    [2020-04-03 10:32:49.090683] [warn] jordan not found in global index country code data so skipping this country

If we search for 'jordan' in `country-codes.txt` we see that MaxMind calls it
'hashemite-kingdom-of-jordan' while speedtest.net simply called it 'jordan'. So
edit `country-codes.txt` to say this instead:

    jordan jo

Keep editing `country-codes.txt` to agree with speedtest.net's spelling of
country names until there are no more warnings when you run this script. You
might need to reach for DuckDuckGo for help as not all of these are obvious.
For example: swaziland is eswatini.
