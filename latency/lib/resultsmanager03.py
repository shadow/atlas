import json
import os
from threading import Thread, Event, RLock
from queue import Empty, Queue
import fcntl
import urllib
from ripe.atlas.cousteau import AtlasLatestRequest
import time


class ResultsManager:
    def __init__(self, args, log, end_event):
        self._args = args
        self._log = log
        self._end_event = end_event
        self._input = Queue(maxsize=1)
        self._thread = Thread(target=self._enter)
        self._thread.name = 'results'
        self._thread.start()
        self._data = {}
        self._lock = RLock()
        self._write_every = 1
        if os.path.isfile(args.all_pairs_measurements):
            self._read_data()

    def wait(self):
        assert self._thread != None
        self._thread.join()

    def _read_data(self):
        log = self._log
        args = self._args
        log('Reading data from', args.all_pairs_measurements)
        with self._lock:
            with open(args.all_pairs_measurements, 'rt') as fd:
                for line in fd:
                    words = line.split()
                    msm_id, target, probes = words[0], words[1], words[2:]
                    msm_id = int(msm_id)
                    probes = [int(p) for p in probes]
                    if msm_id in self._data:
                        log.warn('Msm', msm_id, 'already loaded. overwriting')
                    self._data[msm_id] = {'target': target, 'probes': probes }
        log('Now know of', len(self._data), 'existing measurements')

    def _write_data(self):
        log = self._log
        args = self._args
        log('Writing data to', args.all_pairs_measurements)
        with self._lock:
            with open(args.all_pairs_measurements, 'wt') as fd:
                for msm_id in self._data:
                    fd.write('{} {} {}\n'.format(
                        msm_id, self._data[msm_id]['target'],
                        ' '.join([str(p) for p in self._data[msm_id]['probes']])))

    def _process(self, item):
        log = self._log
        msm_id = item['msm_id']
        inmsm = item['inmsm']
        with self._lock:
            if msm_id in self._data:
                log.warn('Already have msm', msm_id, 'overwriting')
            self._data[msm_id] = {
                'target': inmsm.target,
                'probes': sorted(inmsm.probes),
            }

    def _enter(self):
        log = self._log
        log('Starting', self._thread.name)
        count = 0
        while not self._input.empty() or not self._end_event.is_set():
            try: item = self._input.get(timeout=0.5)
            except Empty: continue
            if item:
                self._process(item)
                count += 1
                if count >= self._write_every:
                    self._write_data()
                    count = 0
        self._write_data()
        log('Ending', self._thread.name)

    def recv(self, msm_id):
        self._input.put(msm_id)

    def have_inmsm(self, inmsm):
        log = self._log
        target = inmsm.target
        probes = sorted(inmsm.probes)
        have = False
        with self._lock:
            for msm_id in self._data:
                msm = self._data[msm_id]
                if msm['target'] == target:
                    if msm['probes'] == probes:
                        return True
            return False
