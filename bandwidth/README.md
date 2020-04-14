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
  `www.speedtest.net/reports-parsed/brazil.txt`. You need to name them
  `$COUNTRY.txt` where `$COUNTRY` is exactly as the country name appears in the
  left column of `data/country-codes.txt`. If you don't you'll get warnings
  later.

For a "simple" table:

    <www.speedtest.net/reports/egypt.html ./03.1-parse-simple-table.py |\
    tee www.speedtest.net/reports-parsed/egypt.txt
    
For a "complex" table:

    <www.speedtest.net/reports/brazil.html ./03.1-parse-complex-table.py |\
    tee www.speedtest.net/reports-parsed/brazil.txt

Once you've done this for all the countries with city data, it's time to start
running `03-parse-data.py` repeatedly until it completes without warnings or
errors.

Verify there's still no issues parsing country data:

    $ ./03-parse-data.py
    [2020-04-08 09:51:04.072371] [debug] Creating PastlyLogger instance
    [2020-04-08 09:51:04.073512] [notice] Loading country data from www.speedtest.net/global-index
    ... verify only debug "Found data" lines here ...
    [2020-04-08 09:51:04.335361] [notice] Loading city data from www.speedtest.net/reports-parsed
    ... additional debug/warn lines here are okay ...
    [2020-04-08 09:56:05.442555] [debug] Deleting PastlyLogger instance

Okay so country data is still fine. Time to address warnings regarding city
data.

    [2020-04-08 09:56:05.437448] [warn] hong-kong not found in global index country code data so skipping www.speedtest.net/reports-parsed/hong-kong.txt

Oops I used `hong-kong.txt` instead of (*checks data/country-codes.txt*)
`hong-kong-(sar).txt`. Silly me. What a obvious mistake. I rename the former to
the latter to fix this warning, and address all other warnings of this nature
in the same way.

In 2020 I put in a ton of effort to programtically handle all of the existing
"edge cases." If you can run `./03-parse-data.py` at this point with no warning
lines being output, then you're done.

    $ ./03-parse-data.py | grep warn | wc -l
    0
    $ # Thank god I'm done and there's no more work to do. Thanks 2020 Matt!

If, however, you do get errors, I now need to divide your attention between the
source of the script and the following paragraphs. You may need to edit the
script and as I've documented how it works *there*. Start with `def
load_city_reports(...)`.

There are two warnings I would expect you to get, and I will now walk you
through how I solved them. The examples are cases that I already have solved
(worked for me in 2020!), thus you shouldn't see them exactly. I hope by
describing my problem solving process for some of these you will be able to do
the same or similar things for any new cities that come up.

### Warning 1: Did not find city "foo" (country "bar") in GeoLite2 CSV DB. Ignoring it.

None of the fiddling the script did could unearth even a single row in
MaxMind's DB that matches this city.

**Example**: Taif/saudi-arabia

    $ grep Taif data/GeoLite2-City-Locations-en.csv
    # outputs nothing

Hmmmm. To DuckDuckGo! <https://duckduckgo.com/?q=taif>
Ah it's spelled "Ta'if". Let's try that.

    $ grep Ta\'if data/GeoLite2-City-Locations-en.csv
    107968,en,AS,Asia,SA,"Saudi Arabia",02,"Makkah Province",,,Ta'if,,Asia/Riyadh,0

Perfect, just one result. Let's add that to the map in `try_alt_name(...)`.

**Example**: Al Hofuf/saudi-arabia

Same thing as before: no results with grep for "Hofuf". Off to DuckDuckGo.
<https://duckduckgo.com/?q=Al+Hofuf>

Hmmm ... and to Wikipedia from there. <https://en.wikipedia.org/wiki/Hofuf>

Lots of alternative spellings in the first paragraph here. Let's pick one.

    $ grep Hufuf data/GeoLite2-City-Locations-en.csv
    109571,en,AS,Asia,SA,"Saudi Arabia",04,"Eastern Province",,,"Al Hufuf",,Asia/Riyadh,0

Perfect, just one result (and the others don't produce any relevant results).
Add it to the map in `try_alt_name(...)`.

**Example**: Sha Tin District/hong-kong

Let's do a grep.

    $ grep 'Sha Tin' data/GeoLite2-City-Locations-en.csv
    1818628,en,AS,Asia,HK,"Hong Kong",NST,"Sha Tin",,,"Tai Wai",,Asia/Hong_Kong,0
    1818781,en,AS,Asia,HK,"Hong Kong",NST,"Sha Tin",,,"Siu Lek Yuen",,Asia/Hong_Kong,0
    1818916,en,AS,Asia,HK,"Hong Kong",NST,"Sha Tin",,,"Sha Tin Wai",,Asia/Hong_Kong,0
    1818920,en,AS,Asia,HK,"Hong Kong",NST,"Sha Tin",,,Shatin,,Asia/Hong_Kong,0
    1819135,en,AS,Asia,HK,"Hong Kong",NST,"Sha Tin",,,"Pak Tin",,Asia/Hong_Kong,0
    1819400,en,AS,Asia,HK,"Hong Kong",NST,"Sha Tin",,,"Ma On Shan Tsuen",,Asia/Hong_Kong,0
    1819417,en,AS,Asia,HK,"Hong Kong",NST,"Sha Tin",,,"Ma Liu Shui",,Asia/Hong_Kong,0
    1819855,en,AS,Asia,HK,"Hong Kong",NST,"Sha Tin",,,"Fo Tan",,Asia/Hong_Kong,0

By the way, the column with `"Sha Tin"` for every row is *not* the city name.
The city name is the forth-from-last column (`"Tai Wai"` for the first row).

From here, and with most of the Hong Kong districts, you have to make a choice
for which city to map to. For Sha Tin District specifically, I chose Shatin,
because -- since I know nothing about HK -- it seems like it must be the
biggest city in Sha Tin District.

### Warning 2: 2 matches for "foo" (country bar) and couldn't pick best, so ignoring.

The script narrowed the list of possible rows and handled them to
`get_best_match(...)`, but it failed to return any match at all.

It is tempting to patch `get_best_match` to always return one of the rows given
if it can't figure out which is the best, but I saw rows make it in to this
function with cities (with similar names) in two different countries. Thus I
don't think that would be smart. I did, however, decide to pick an arbitrary
row if there were still 2+ rows after matching on the correct country.

Anyway, let's look at examples.

**Example**: Brisbane, Queensland/australia

What has happened here is `load_city_reports(...)` tried the full "Brisbane,
Queensland" as the city name, which didn't work, then it tried "Brisbane"
as the city and got more than one Brisbane-named city. Indeed, there's a
Brisbane in California that it got:

    # leading comma in grep to avoid the flood of cities that are in the
    # Australia/Brisbane timezone
    $ grep ',Brisbane' data/GeoLite2-City-Locations-en.csv
    2174003,en,OC,Oceania,AU,Australia,QLD,Queensland,,,Brisbane,,Australia/Brisbane,0
    5330810,en,NA,"North America",US,"United States",CA,California,,,Brisbane,807,America/Los_Angeles,0

So it passes these two rows to `get_best_match(...)`, which notices the comma
in "Brisbane, Queensland" (the `city_name` it receives). It treats Queensland
as a subdivision between Australia and Brisbane, and with that is able to
narrow it down to just the Australian row. Tada!

**Example**: Ghent/belgium

This is simple enough. The script found three Ghents:

    $ grep Ghent data/GeoLite2-City-Locations-en.csv
    36402:2797656,en,EU,Europe,BE,Belgium,VLG,Flanders,VOV,"East Flanders Province",Ghent,,Europe/Brussels,1
    90120:4292709,en,NA,"North America",US,"United States",KY,Kentucky,,,Ghent,529,America/New_York,0
    101086:5118481,en,NA,"North America",US,"United States",NY,"New York",,,Ghent,532,America/New_York,0

`get_best_match(...)` filtered on the country name and found just one Ghent in
Belgium. Tada!
