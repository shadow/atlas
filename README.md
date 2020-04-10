# I will be force pushing over this repo to rewrite its history without data

^ Just a fair warning.

Create a virtualenv and install all requirements

    virtualenv -p /usr/bin/python3 atlasvenv
    source atlasvenv/bin/activate
    pip install -r latency/requirements.txt
    pip install -r bandwidth/requirements.txt
    pip install -r glue/requirements.txt

# Latency

See `latency/README.md` for more info than what is here.

This process will cost you about 10 million RIPE Atlas credits, probably more
as time passes and RIPE gains more nodes.

This process will take you weeks. Spread your RIPE Atlas credits across your
co-author's accounts and use their API keys too to help shorten the duration.

# Bandwidth

See `bandwidth/README.md` for more info than what is here.

This process is a good thing to work on while you're letting the latency step
run.

Also this process really really sucks. Find your worst intern or grad student
who needs punishing. I'm sorry, but it was never going to be easy to automate
the parsing of webpages that (1) are meant to look good for human consumption,
(2) make no guarantee of stability from year to year, and (3) never said they'd
call countries/cities the same name with the same spelling as some *other*
Internet company.

If you're lucky, the current date is really close to April 2020 and not much,
if anything, has changed on speedtest.net's pages. Most likely there will be
some new data and some warnings you need to fix. If you're unlucky, they've
moved or just deleted the reports for which these scripts are written.

# Glue

This takes the previous two steps and glues them together for the final network
topoloy.
