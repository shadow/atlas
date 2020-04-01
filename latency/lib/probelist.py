import os
import json
from datetime import datetime, timedelta
import urllib.request
import fcntl


class ProbeList:
    def __init__(self, args, log, mmdb):
        self._args = args
        self._log = log
        self._mmdb = mmdb
        fname = args.probe_list
        if not os.path.exists(fname):
            log.notice(args.probe_list, 'doesn\'t exist. Need to get it')
            self._probes = ProbeList._fetch_all_probes(log, fname)
            log.notice('Saving probes to', args.probe_list)
            with open(fname, 'wt') as fd:
                json.dump(self._probes, fd, indent=2)
        elif os.path.exists(fname):
            max_age = args.probe_list_age
            t = (datetime.now() - timedelta(hours=max_age)).timestamp()
            if os.path.getmtime(fname) > t:
                log.info('Already have', fname, 'and it\'s still fresh.')
                with open(fname, 'rt') as fd:
                    self._probes = json.load(fd)
            else:
                log.info('Probe cache too old. Fetching again.')
                self._probes = ProbeList._fetch_all_probes(log, fname)
                with open(fname, 'wt') as fd:
                    json.dump(self._probes, fd, indent=2)
        log.notice(len(self._probes), 'probes known')

    @staticmethod
    def lock_fd(fd):
        fcntl.flock(fd, fcntl.LOCK_EX)

    @staticmethod
    def unlock_fd(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)

    @staticmethod
    def _fetch_all_probes(log, fname):
        probes = []
        last_probe_id = -1
        log.debug('Fetching probes after id',last_probe_id)
        url = 'https://atlas.ripe.net/api/v2/probes/?page_size=500&'\
                'status_name=Connected&is_public=true'
        probe_resp = urllib.request.urlopen(url+"&id__gt="+str(last_probe_id))
        j = json.loads(probe_resp.read().decode("utf-8"))
        while len(j["results"]):
            old_len = len(probes)
            log.debug("found",len(j["results"]),"probes")
            for p in j["results"]:
                last_probe_id = p["id"]
                if ProbeList._is_good_probe(p): probes.append(p)
            new_len = len(probes)
            log.debug('of which',new_len-old_len,'had an ipv4 addr')
            log.debug('Fetching probes after id',last_probe_id)
            probe_resp = urllib.request.urlopen(url+"&id__gt="+str(last_probe_id))
            j = json.loads(probe_resp.read().decode("utf-8"))
        return probes

    @staticmethod
    def _is_good_probe(probe):
        ip = probe["address_v4"]
        if not ip: return False
        tags = probe["tags"]
        for tag in tags:
            if tag["slug"] == "system-ipv4-works": return True
        return False

    def group_probes_by_city(self):
        log = self._log
        mmdb = self._mmdb
        self._city_groups = {}
        next_unknown_city_code = -1
        no_city = 0
        for probe in self._probes:
            ip = probe['address_v4']
            data = mmdb.get(ip)
            if not data or 'city' not in data:
                city_code = next_unknown_city_code
                #next_unknown_city_code -= 1
                no_city += 1
            else:
                city_code = data['city']['geoname_id']
            if city_code not in self._city_groups:
                self._city_groups[city_code] = []
            self._city_groups[city_code].append(probe)
        log(len(self._city_groups), 'city groups from', len(self._probes),
            'probes and', no_city, 'probes without city data')

    def add_reachability_info(self):
        args = self._args
        log = self._log
        reachable_results = 0
        total_results = 0
        with open(args.measurements_file, 'rt') as fd:
            ProbeList.lock_fd(fd)
            try: measurements = json.load(fd)
            finally: ProbeList.unlock_fd(fd)
        for prb_id in measurements:
            if not 'result' in measurements[prb_id]: continue
            result = measurements[prb_id]['result']
            if len(result) < 1:
                log.warn('There is no result from prb', prb_id, '???')
                continue
            if len(result) != 1:
                log.warn('length of result from prb', prb_id, 'is', len(result),
                         'taking the first')
            total_results += 1
            result = result[0]
            avg_rtt = result['avg']
            is_reachable = avg_rtt > 0
            if is_reachable:
                reachable_results += 1
            for probe in self._probes:
                if str(probe['id']) == str(prb_id):
                    probe['reachable'] = is_reachable
                    #log.debug('Marking prb', prb_id, 'as reachable', is_reachable)
                    break
        log('{}/{} probes with results were reachable.'
            .format(reachable_results, total_results))

    def trim_unreachable(self):
        log = self._log
        total, trimmed_unknown, trimmed_unreachable = 0, 0, 0
        new_probes = []
        for probe in self._probes:
            total += 1
            if 'reachable' not in probe:
                trimmed_unknown += 1
                continue
            if not probe['reachable']:
                trimmed_unreachable += 1
                continue
            new_probes.append(probe)
        log('Keeping {}/{} probes after trimming {} with unknown reachability '
            'and {} unreachable'.format(len(new_probes), total, trimmed_unknown,
                                        trimmed_unreachable))
        self._probes = new_probes

    def keep_only_best(self):
        args = self._args
        log = self._log
        assert self._city_groups
        kept_probes = []
        for city in self._city_groups:
            assert len(self._city_groups[city]) > 0
            self._city_groups[city].sort(key=lambda p: p['total_uptime'],
                                         reverse=True)
            #log(city, ':', *[p['total_uptime'] for p in self._city_groups[city]])
            kept_probes.append(self._city_groups[city][0])
        log('Kept the best', len(kept_probes), 'probes. Writing to',
            args.out_selected_probes)
        self._probes = kept_probes
        with open(args.out_selected_probes, 'wt') as fd:
            json.dump(self._probes, fd, indent=2)

    def generate_all_pairs(self):
        args = self._args
        log = self._log
        all_pairs = []
        for i, target_probe in enumerate(self._probes):
            for j, source_probe in enumerate(self._probes[i+1:]):
                all_pairs.append((int(target_probe['id']), int(source_probe['id'])))
        log(len(all_pairs), 'all pairs')
        current_target = None
        groups = []
        for pair in all_pairs:
            if current_target is None or pair[0] != current_target or len(groups[-1]) >= args.max_probes_per_measurement:
                if len(groups) > 0:
                    #log.debug('Ending group with len', len(groups[-1]))
                    pass
                groups.append(set())
                current_target = pair[0]
            groups[-1].add(pair)
        log(len(groups), 'groups to measure')
        # make sure all pairs have the same first element
        for group in groups:
            group_target = None
            for pair in group:
                if group_target is None:
                    group_target = pair[0]
                    continue
                assert group_target == pair[0]
        with open(args.out_all_pairs_list, 'wt') as fd:
            for group in groups:
                # weird hack, but safe bc all pairs have the same first element
                target_id = None
                for pair in group:
                    if target_id is None:
                        target_id = pair[0]
                        break
                # </end hack>
                target_ip = None
                for probe in self._probes:
                    if int(probe['id']) == int(target_id):
                        target_ip = probe['address_v4']
                        break
                assert target_ip
                source_ids = [pair[1] for pair in group]
                fd.write('{} {}\n'.format(target_ip, ' '.join([str(s) for s in source_ids])))


    def assert_all_probes_have_city(self):
        mmdb = self._mmdb
        for p in self._probes:
            data = mmdb.get(p['address_v4'])
            assert data and 'city' in data

    @property
    def probes_with_a_city(self):
        mmdb = self._mmdb
        for p in self._probes:
            data = mmdb.get(p['address_v4'])
            if not data or 'city' not in data:
                continue
            yield p

    @property
    def num_probes_with_a_city(self):
        mmdb = self._mmdb
        count = 0
        for p in self._probes:
            data = mmdb.get(p['address_v4'])
            if not data or 'city' not in data:
                continue
            count += 1
        return count
