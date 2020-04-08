#!/usr/bin/env python3
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from lib.pastlylogger import PastlyLogger
import csv
import re
import os
import json
import glob
log = PastlyLogger(debug='/dev/stdout', overwrite=['debug'], log_threads=False)


def fail_hard(*a):
    log.error(*a)
    exit(1)


def expand_path(path, user=True, vars=True, norm=True, abs=True):
    ''' Optionally expand path using the various os.path functions.
    I could explain each of these, or I could just point to
    https://docs.python.org/3.4/library/os.path.html (fix for your version of
    python as necessary) '''
    if user:
        path = os.path.expanduser(path)
    if vars:
        path = os.path.expandvars(path)
    if norm:
        path = os.path.normpath(path)
    if abs:
        path = os.path.abspath(path)
    return path


def find_files(d, ext=None):
    ''' Recursively find all files in the specified dir, optionally limited
    to files with the specified extension '''
    files = set()
    for root, subdirs, subfiles in os.walk(d):
        for fname in subfiles:
            fname = os.path.join(root, fname)
            if not ext:
                files.add(fname)
            else:
                fbase, fext = os.path.splitext(fname)
                if fext == ext:
                    files.add(fname)
    return files


def _trim_global_index_data(args, data):
    best_upload = None
    best_download = None
    country_name = None
    country_id = None
    # The data coming is is essentially two lists: fixed and mobile.
    # Each list has dictionaries of monthly summaries.
    # Find the highest upload and download rates and return them as the
    # up/download rates for the country.
    # Country ID is an integer. Not sure what it maps to yet. It would be nice
    # if it was an ID MaxMind understood, but I'm not getting my hopes up.
    for connection_type in ['fixed', 'mobile']:
        data_list = data[connection_type]
        for item in data_list:
            if best_upload is None:
                best_upload = float(item['upload_mbps'])
            elif float(item['upload_mbps']) > best_upload:
                best_upload = float(item['upload_mbps'])
            if best_download is None:
                best_download = float(item['download_mbps'])
            elif float(item['download_mbps']) > best_download:
                best_download = float(item['download_mbps'])
            if country_name is None:
                country_name = item['country']['country_name']
            if country_id is None:
                country_id = item['country']['country_id']
    return {'up_mbits': best_upload,
            'down_mbits': best_download,
            'country_name': country_name,
            'country_id': country_id, }


def load_global_index(args, gicc):
    directory = os.path.join(args.dir, 'global-index')
    if not os.path.exists(directory) and not os.path.isdir(directory):
        log.warn('Could not find country data')
        return {}
    data = {}
    log.notice('Loading country data from', directory)
    reg = r'^ *var data = ({.+});$'
    fnames = find_files(directory)
    for fname in fnames:
        fbase, _ = os.path.splitext(fname)
        fbase = os.path.basename(fbase)
        with open(fname, 'rt') as fd:
            for line in fd:
                match = re.search(reg, line)
                if not match:
                    continue
                log.debug('Found data for', fbase)
                if fbase in data:
                    log.warn('Already had data for', fbase, 'overwriting it')
                if fbase not in gicc:
                    log.warn(fbase, 'not found in global index country code '
                             'data so skipping this country')
                    continue
                cc = gicc[fbase]
                data[cc] = json.loads(match.group(1))
                data[cc] = _trim_global_index_data(args, data[cc])
    return data


def sets_of_n(lst, n):
    out = []
    work = []
    for item in lst:
        work.append(item)
        if len(work) == n:
            out.append(work)
            work = []
    assert not len(work)
    return out


def rows_with_city(csv_dict, city_name):
    rows = []
    city_name = city_name.lower()
    for row in csv_dict:
        if row['city_name'].lower() == city_name:
            rows.append(row)
    return rows


def get_best_match(rows, city_name, country_name):
    ''' Other functions whittled down the entire MaxMind CSV database into a
    much smaller set of rows. Now it's time for this function to choose which
    of them is the best match for the given city and country.

    This function will either return one row or the value None. If the caller
    wants to work with a list of rows, it's up to them to wrap a non-None
    return value from us in a list.
    '''
    assert len(rows)
    if len(rows) == 1:
        return rows[0]
    # if the city name has a comma in it, try treating the part after the comma
    # as a "subdivision" (state, in the US) name. There's two levels of
    # subdivisions in maxmind's db. This part tries subdiv level 1
    if ',' in city_name:
        log.debug(
            f'Trying to find best match for {city_name} from {len(rows)} '
            f'rows with subdiv level 1')
        city, subdiv = city_name.split(',', maxsplit=1)
        city = city.lower()
        # replace fancy e with simple e because Quebec
        subdiv = subdiv.strip().lower().replace('é', 'e')
        filtered = []
        for row in rows:
            if row['city_name'].lower() != city:
                continue
            if row['subdivision_1_name'].lower() == subdiv:
                filtered.append(row)
        if len(filtered) == 1:
            return filtered[0]
        if len(filtered) > 1:
            log.info(
                f'Still {len(filtered)} matches for "{city}" city in subdiv '
                f'"{subdiv}" in country {country_name}. Arbitrarily picking '
                'first of the following')
            for row in filtered:
                log.debug(dict(row))
            return filtered[0]
    # if no comma in city_name, try filtering on country name matches
    if ',' not in city_name:
        # replace - with ' ' because saudi-arabia
        country = country_name.lower().replace('-', ' ')
        log.debug(
            f'There exists {len(rows)} matches for "{city_name}" city. '
            f'Trying to filter down with "{country}" country')
        filtered = []
        for row in rows:
            if row['country_name'].lower() == country:
                filtered.append(row)
        if len(filtered) == 1:
            return filtered[0]
        if len(filtered) > 1:
            log.info(
                f'More than one match for "{city_name}" city with "{country}" '
                f'country name. Arbitrarily picking the first item of the '
                f'following {len(filtered)}')
            for row in filtered:
                log.debug(dict(row))
            return filtered[0]
    return None


def try_alt_name(mmdb_csv, city):
    ''' speedtest.net and MaxMind spell some cities differently. This handles
    those cases. Not that it only calls rows_with_city(...) with the new city
    name and doesn't try other things. If it returns multiple rows, it's up to
    the caller to figure out which is best.
    '''
    alt_name_map = {
        'Buraydah': 'Buraidah',
        'Yekaterinburg': 'Ekaterinburg',
        'Saint Petersburg': 'St Petersburg',
        'Nizhny Novgorod': 'Nizhniy Novgorod',
        'Al Khobar': 'Khobar',
        'Al Hofuf': 'Al Hufuf',
        'Taif': 'Ta\'if',
        'Shubra al Khaymah': 'Shubra',
        'Al Mahalla El Kubra': 'Al Mahallah al Kubra',
        'Saint Petersburg, Florida': 'St Petersburg',
        'Québec City, Québec': 'Québec',
        'Sha Tin District': 'Shatin',
        'Wan Chai District': 'Wanchai',
        # there are three "cities" in this district, this is one of them
        'Yau Tsim Mong District': 'Yau Ma Tei',
        # there are ~eight "cities" in this district, this is one of them
        'Central and Western District': 'Tai Hang',
        'Kowloon City District': 'Kowloon',
        # there are ~ten "cities" in this district, this is one of them
        'Southern District': 'Deep Water Bay',
        # there are ~nine "cities" in this district, this is one of them
        'Eastern District': 'Sai Wan Ho',
        'Las Palmas': 'Las Palmas de Gran Canaria',
    }
    if city in alt_name_map:
        return rows_with_city(mmdb_csv, alt_name_map[city])
    return []



def load_city_reports(args, gicc, mmdb_csv):
    ''' This is the primary function responsible for parsing the city data from
    speedtest.net into the final usable form. As input we take:

        - args, the command line args. Used to get the directory the
        partially-parsed speedtest.net city data is in.
        - gicc, the "global index country codes". Just a simple country name ->
        code dictionary parsed from data/country-codes.txt by default.
        - mmdb_csv, the MaxMind GeoLite2 city database in CSV format.

    This function outputs a dictionary. Keys are the geoname_id city codes.
    Values are a dictionary of the following:
        - the name of the country in which the city is located
        - the 2-letter country code for that country
        - the name of the city
        - the bandwidth up in that city, in Mbit/s
        - the bandwidth down in that city, in Mbit/s
        - the geoname_id of the city
    '''
    out_data = {}
    directory = os.path.join(args.dir, 'reports-parsed')
    if not os.path.exists(directory) and not os.path.isdir(directory):
        log.warn('Could not find reports-parsed directory with city data')
        return {}
    assert os.path.exists(directory) and os.path.isdir(directory)
    log.notice('Loading city data from', directory)
    # recursively look for files in the fornmat COUNTRY_NAME.txt where
    # COUNTRY_NAME is a country name, spelled exactly like it is in the gicc.
    for fname in glob.iglob(f'{directory}/**', recursive=True):
        if not os.path.isfile(fname):
            continue
        country = os.path.splitext(os.path.basename(fname))[0]
        if country not in gicc:
            log.warn(country, 'not found in global index country code data '
                     'so skipping', fname)
            continue
        # We have city data from a known country. It's parsin' time. The data
        # comes three lines at a time, so we look at the input lines in groups
        # of 3. First line city name, second is down bandwidth, third is up
        # bandwidth (both in Mbit/s)
        lines = iter([line.strip() for line in open(fname, 'rt')])
        for city, down, up in sets_of_n(lines, 3):
            # Look for a SINGLE EXACT match for the given city name in
            # mmdb_csv. Spolier alert: this won't find anything most of the
            # time.
            rows = rows_with_city(mmdb_csv, city)
            # If there are still no rows ...
            # Many city names as spelled by speedtest.net are actually "City,
            # State" (or similar for places that don't call them states). So
            # let's try the same thing again, but with just the city part.
            if not len(rows) and ',' in city:
                city_ = city.split(',')[0]
                rows = rows_with_city(mmdb_csv, city_)
            # If there are still no rows ...
            # Hong Kong is broken up into districts, and some (but not even
            # close to all) of those districts can be found as cities by simply
            # removing the word "District". So let's try the same thing again,
            # but without the " District" suffix.
            if not len(rows) and city.endswith(' District'):
                city_ = city[:-1*len(' District')]
                rows = rows_with_city(mmdb_csv, city_)
            # If there are still no rows ...
            # Jump into a separate function that handles more complex cases of
            # "speedtest.net spells it this way, but MaxMind spells it this
            # other way."
            if not len(rows):
                rows = try_alt_name(mmdb_csv, city)
            # If there are still now rows ... fucking give up, man.
            #
            # If you get this warning, the easiest thing to do may be to add
            # another mapping in try_alt_name(...).
            if not len(rows):
                log.warn(f'Did not find city "{city}" (country {country}) '
                         f'in GeoLite2 CSV DB. Ignoring it.')
                continue
            # More than 1 row is an improvement. But now we need to decide on
            # which one. Jump into a separate function that picks the best one.
            if len(rows) > 1:
                best_match = get_best_match(rows, city, country)
                if best_match is None:
                    log.warn(
                        f'{len(rows)} matches for "{city}" (country '
                        f'{country}) and couldn\'t pick best, so ignoring.')
                    for r in rows:
                        log.debug(dict(r))
                    continue
                rows = [best_match]
            # Yay there's just one row left at this point! Store it and move on
            # to the next.
            assert len(rows) == 1
            row = rows[0]
            out_data[row['geoname_id']] = {
                'country_name': country,
                'country_id': gicc[country],
                'city_name': row['city_name'],
                'up_mbits': up,
                'down_mbits': down,
                'city_id': int(row['geoname_id'])
            }
    return out_data


def load_global_index_country_codes(args):
    assert os.path.isfile(args.gicc)
    d = {}
    with open(args.gicc, 'rt') as fd:
        for line in fd:
            line = line.strip()
            name, code = line.split(' ')
            d[name] = code.upper()
    return d


def load_mmdb_csv(args):
    return [row for row in csv.DictReader(open(args.mmdb_csv, 'rt'))]


def main(args):
    gicc = load_global_index_country_codes(args)
    mmdb_csv = load_mmdb_csv(args)
    global_index = load_global_index(args, gicc)
    city_reports = load_city_reports(args, gicc, mmdb_csv)
    with open(args.output, 'wt') as fd:
        json.dump({'countries': global_index, 'cities': city_reports},
                  fd, indent=2)


if __name__ == '__main__':
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--dir', type=str, default='www.speedtest.net',
                        help='Path to speedtest.net wget dump directory')
    parser.add_argument('-o', '--output', type=str, default='speed-data.json')
    parser.add_argument('--gicc', type=str,
                        default='data/country-codes.txt',
                        help='Path to file storing country names and codes '
                        'as used in the speedtest.net/global-index webpages')
    parser.add_argument('--mmdb-csv', type=str,
                        default='data/GeoLite2-City-Locations-en.csv',
                        help='Path to the GeoLite2 City database in CSV '
                        'format that you downloaded.')
    args = parser.parse_args()
    if not os.path.exists(args.gicc) and not os.path.isfile(args.gicc):
        fail_hard(args.gicc, 'doesn\'t exist')
    exit(main(args))
