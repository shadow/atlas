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

Create an empty cities-related file for now. We'll come back to it later.

    touch data/maxminddb-cities.csv

## Countries

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

## Cities

This is going to suck. This is a pretty manual process.

Create `www.speedtest.net/reports` and `www.speedtest.net/reports-parsed`.
Visit <https://speedtest.net/reports/> in your browser.

Some of the countries listed have "simple" tables that *should* be parseable
with `03.1-parse-simple-table.py`. Some have "complex" tables that *should* be
parseable with `03.1-parse-complex-table.py`. Some don't have the data we want.

In 2020 the following countires have **simple** tables:

- Egypt (2016 report)
- Hong Kong (2016 report)

See `example-simple-table.png` for Egypt's table.

In 2020 the following countries have **complex** tables:

- Brazil (2018 fixed)
- Canada (2019 fixed)
- United States (2018 fixed)
- Saudi Arabia (2018 fixed)
- Australia (2017 fixed)
- Belgium (2018 fixed)
- Ireland (2018 fixed)
- Russia (2018 fixed)
- Spain (2018 fixed)
- United Kingdom (2018 fixed)

See `example-complex-table.png` for Brazil's table.

In 2020, the following countries/regions did **not** have city data:

- Central America (it has countries)
- Mexico
- Peru
- Singapore
- Germany
- Italy (2018 fixed) (it was actually mobile, not fixed, data)
- Nordic Countries (it has countries)
- Turkey

For each of the page that actually does have usable data:

- Visit the page.
- Copy the table's HTML into a file in `www.speedtest.net/reports`. E.g.
  `www.speedtest.net/reports/brazil.html`. I found it easiest to use Chrome's
  dev console, inspect the table, and copy the `<table>` element's HTML from
  there.
- Run `03.1-parse-simple-table.py` (or the complex script, as applicable) with
  the table html file as input. Pipe the output into a a file in
  `www.speedtest.net/reports-parsed` such as
  `www.speedtest.net/reports-parsed/brazil.txt`.


    # for a "simple" table
    <www.speedtest.net/reports/egypt.html ./03.1-parse-simple-table.py |\
    tee www.speedtest.net/reports-parsed/egypt.txt
    
    # for a "complex" table
    <www.speedtest.net/reports/brazil.html ./03.1-parse-complex-table.py |\
    tee www.speedtest.net/reports-parsed/brazil.txt
