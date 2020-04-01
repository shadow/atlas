#!/usr/bin/env python3
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from lib.pastlylogger import PastlyLogger
from lib.probelist import ProbeList
from lib.resultsmanager import ResultsManager
from lib.atlasclient import AtlasClient
import os
import maxminddb
import time
import json
from queue import Empty, Queue
from threading import Thread, Event
from urllib.request import Request, urlopen
from urllib.error import HTTPError
log = PastlyLogger(debug='/dev/stdout', overwrite=['debug'], log_threads=True)
#log = PastlyLogger(info='/dev/stdout', overwrite=['info'], log_threads=True)
#log = PastlyLogger(notice='/dev/stdout', overwrite=['notice'], log_threads=True)
def fail_hard(*s):
    if s: log.error(*s)
    exit(1)

kill_worker_threads = Event()
kill_stats_thread = Event()
start_time = time.time()
progress = None
progress_end = None
previously_existing_progress = 0

class Worker:
    def __init__(self, args, log, results_manager, end_event, name):
        self._args = args
        self._log = log
        self._rm = results_manager
        self._name = name
        self._end_event = end_event
        self._input = Queue(maxsize=1)
        self._thread = Thread(target=self._enter)
        self._thread.name = self._name
        self._thread.start()

    def wait(self):
        assert self._thread != None
        self._thread.join()

    def give(self, item):
        self._input.put(item)

    @property
    def name(self): return self._name
    @property
    def is_ready(self): return not self._input.full()

    def _enter(self):
        log = self._log
        log('Starting Worker', self._name)
        atlas_client = AtlasClient(self._args, self._log, self._rm)
        while not self._input.empty() or not self._end_event.is_set():
            item = None
            try: item = self._input.get(timeout=0.5)
            except Empty: continue
            if item:
                atlas_client.do(item)
        log('Ending Worker', self._name)


def get_next_worker_thread(workers):
    while True:
        for w in workers:
            if w.is_ready:
                return w
        time.sleep(0.005)


def remaining_time(current_item, total_items, current_runtime):
    if current_item < 1:
        VERY_BIG_NUMBER = 60*60*24*365*10
        return VERY_BIG_NUMBER
    rem = ((current_runtime * total_items) / current_item) - current_runtime
    return rem


def seconds_to_duration(secs):
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    d, h, m, s = int(d), int(h), int(m), int(round(s,0))
    if d > 0: return '{}d{}h{}m{}s'.format(d,h,m,s)
    elif h > 0: return '{}h{}m{}s'.format(h,m,s)
    elif m > 0: return '{}m{}s'.format(m,s)
    else: return '{}s'.format(s)


def log_stats():
    now = time.time()
    dur = seconds_to_duration(now - start_time)
    rem = seconds_to_duration(remaining_time(progress, progress_end, now - start_time))
    log.notice('We\'ve been running for', dur, 'have handled',
            '{}/{}'.format(progress, progress_end), 'measurements, and expect to be done in', rem)


def probably_can_create_measurement(args):
    now = time.time()
    if now - 30 < probably_can_create_measurement.last_check:
        log.debug('Returning cached answer',
                  probably_can_create_measurement.last_answer)
        return probably_can_create_measurement.last_answer
    log.debug('Checking again if we can create measurements')
    probably_can_create_measurement.last_check = now
    atlas_url = 'https://atlas.ripe.net/api/v2/credits/'
    req = Request(atlas_url)
    req.add_header('Authorization', 'Key {}'.format(args.api))
    try: resp = urlopen(req)
    except HTTPError as e:
        log.warn('Couldn\'t fetch credit information. Assuming (probably '
                'incorrectly) that we can create more measurements')
        probably_can_create_measurement.last_answer = True
        return True
    j = json.loads(resp.read().decode('utf-8'))
    previous_results = j['past_day_measurement_results']
    if previous_results > args.results_per_day:
        log.info('Previous day had',previous_results,'so need to wait until '
                'that goes down.')
        probably_can_create_measurement.last_answer = False
        return False
    #atlas_url = 'https://atlas.ripe.net/api/v2/measurements/my/?status__in=1,2'
    #req = Request(atlas_url)
    #req.add_header('Authorization', 'Key {}'.format(args.api))
    #try: resp = urlopen(req)
    #except HTTPError as e:
    #    log.warn('Couldn\'t fetch measurement count information. Assuming '
    #             '(probably incorrectly) that we can create more measurements')
    #    probably_can_create_measurement.last_answer = True
    #    return True
    #j = json.loads(resp.read().decode('utf-8'))
    #count = int(j['count'])
    #if count > args.max_concurrent_measurements:
    #    log.info('Too many concurrent measurements. Need to wait')
    #    probably_can_create_measurement.last_answer = False
    #    return False
    probably_can_create_measurement.last_answer = True
    return True
probably_can_create_measurement.last_check = 0
probably_can_create_measurement.last_answer = None


def main(args):
    global progress
    global progress_end
    mmdb = maxminddb.open_database(args.mmdb)
    probe_list = ProbeList(args, log, mmdb)
    results_manager = ResultsManager(args, log)
    return
    atlas_client = AtlasClient(args, log, results_manager)
    workers = [Worker(args, log, results_manager, kill_worker_threads,
                      'Worker-{}'.format(i)) for i in range(0, args.threads)]
    pe = PeriodicEvent(log_stats, _run_interval=args.stats_interval,
                       _end_event=kill_stats_thread, _thread_name='stats')
    progress = 0 - previously_existing_progress
    progress_end = probe_list.num_probes_with_a_city - previously_existing_progress
    for probe in probe_list.probes_with_a_city:
        while not probably_can_create_measurement(args):
            time.sleep(15)
        progress += 1
        worker = get_next_worker_thread(workers)
        log.debug('Giving worker', worker.name, 'probe', probe['id'])
        worker.give({'probe': probe})
    kill_worker_threads.set()
    kill_stats_thread.set()


if __name__ == '__main__':
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--probe-list', type=str, default='cache/all-probes.json',
        help='File in which to store a cache of existing RIPE probes')
    parser.add_argument(
        '--probe-list-age', type=float, default=1000000,
        help='Max age in hours of the probe list before redownloading it')
    parser.add_argument(
        '--mmdb', type=str, default='data/GeoLite2-City.mmdb', help='Path to '
        'MaxMind City DB')
    parser.add_argument(
        '--measurements-file', type=str, default='cache/reachability-measurements.txt',
        help='File to store measurement IDs as they are created')
    parser.add_argument(
        '--src-probe', type=int, default=33415, help='ID of source RIPE Atlas '
        'probe to use to test reachability of other probes')
    parser.add_argument(
        '--api', type=str, required=True, help='RIPE Atlas API Key')
    parser.add_argument(
        '--msm-attempts', type=int, default=3, help='Num times to attempt to '
        'create a measurement')
    parser.add_argument(
        '--msm-result-timeout', type=float, default=300, help='Num of seconds '
        'to wawit for a measurement result')
    parser.add_argument(
        '--threads', type=int, default=1, help='Num threads to make at once')
    parser.add_argument(
        '--stats-interval', type=float, default=300, help='Log progress stats '
        'every this many seconds')
    parser.add_argument(
        '--results-per-day', type=int, default=98000, help='Max num of results '
        'RIPE will allow you to get in one day. Can be near the real limit.')
    args = parser.parse_args()
    if not os.path.isfile(args.mmdb):
        fail_hard(args.mmdb, 'must exist as a file')
    if len(args.api) != 36:
        fail_hard(args.api, 'doesn\'t look like an API key')
    try:
        main(args)
    except KeyboardInterrupt: pass
    finally:
        kill_worker_threads.set()
        kill_stats_thread.set()
