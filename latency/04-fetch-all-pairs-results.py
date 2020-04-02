#!/usr/bin/env python3
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from lib.pastlylogger import PastlyLogger
from ripe.atlas.cousteau import AtlasLatestRequest
import os
import json
import time
log = PastlyLogger(debug='/dev/stdout', overwrite=['debug'], log_threads=True)
#log = PastlyLogger(info='/dev/stdout', overwrite=['info'], log_threads=True)
#log = PastlyLogger(notice='/dev/stdout', overwrite=['notice'], log_threads=True)

def fail_hard(*s):
    if s: log.error(*s)
    exit(1)


def load_all_msm_ids(args):
    assert os.path.isfile(args.measurements)
    msm_ids = set()
    with open(args.measurements, 'rt') as fd:
        for line in fd:
            words = line.strip().split()
            msm_ids.add(str(words[0]))
    log.info('Found', len(msm_ids), 'measurements in', args.measurements)
    return list(msm_ids)
    return


def load_existing_results(args):
    results = {}
    if not os.path.isfile(args.results):
        return results
    with open(args.results, 'rt') as fd:
        results = json.load(fd)
    log.info('Found', len(results), 'existing results in', args.results)
    return results


def write_results(args, results):
    log.info('Writing resutls to', args.results)
    with open(args.results, 'wt') as fd:
        json.dump(results, fd, indent=2)


def fetch_result_for_msm(msm_id):
    req = AtlasLatestRequest(msm_id=msm_id)
    log.debug('Fetching result for', msm_id)
    success, resp = req.create()
    if not success:
        log.warn('Issue fetching results for msm', msm_id, ':', resp)
        return None
    return resp


def main(args):
    msm_ids = load_all_msm_ids(args)
    results = load_existing_results(args)
    count = 0
    need_write = False
    try:
        for msm_id in sorted(msm_ids):
            if msm_id not in results:
                res = fetch_result_for_msm(msm_id)
                time.sleep(0.25)
                if not res: continue
                results[msm_id] = res
                need_write = True
                count += 1
                if count >= args.write_results_every:
                    count = 0
                    write_results(args, results)
                    need_write = False
            #else:
            #    log.debug('Already had result for', msm_id)
    finally:
        if need_write:
            write_results(args, results)
            need_write = False


if __name__ == '__main__':
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--measurements', type=str, default='cache/all-pairs-measurements.txt',
        help='Output from 03-all-pairs-ping.py')
    parser.add_argument(
        '--results', type=str, default='cache/all-pairs-results.json',
        help='Place to store fetched results from RIPE')
    parser.add_argument(
        '--write-results-every', type=int, default=5, metavar='NUM',
        help='Write out all fetched-so-far results every NUM fetches')
    args = parser.parse_args()
    for fname in [args.measurements]:
        if not os.path.isfile(fname):
            fail_hard(fname, 'must exist')
    try: main(args)
    except KeyboardInterrupt: pass
