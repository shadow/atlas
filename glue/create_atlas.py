#!/usr/bin/env python3

import csv
import json
import networkx
import logging

from statistics import mean

PROBES="../latency/data/all-pairs.csv"
SPEEDS="../bandwidth/speed-data.json"

OUTGRAPH="atlas.graphml.xml"

MAX_LATENCY=300.0 # milliseconds
MAX_LOSS=0.015 # 1.5 percent

FORMAT = "%(asctime)s %(filename)s:%(lineno)d:%(funcName)s() %(levelname)s %(message)s"
logging.basicConfig(level=logging.DEBUG, format=FORMAT)

def main():
    logging.info("loading speedtest data from {}...".format(SPEEDS))
    # load speedtest data
    with open(SPEEDS, 'r') as inf:
        speed = json.load(inf)

    speed['global_up_mbit'] = mean([speed['countries'][code]['up_mbits'] for code in speed['countries']])
    speed['global_down_mbit'] = mean([speed['countries'][code]['down_mbits'] for code in speed['countries']])
    logging.info("found global averages: {} mbit/s up, {} mbit/s down".format(speed['global_up_mbit'], speed['global_down_mbit']))

    # since we have multiple latencies for each edge we need to callapse them
    latencies = {'ip2ip':{}, 'city2city':{}, 'country2country': {}, 'global': {}}
    G = networkx.Graph(preferdirectpaths="True")

    logging.info("adding nodes using probes from {}...".format(PROBES))
    # add nodes first
    with open(PROBES, 'r') as inf:
        reader = csv.DictReader(inf, delimiter=',')

        for row in reader:
            src_ip = row['src']
            src_country = row['src_country']
            dst_ip = row['dst']
            dst_country = row['dst_country']
            src_city = int(row['src_city'])  # MaxMind int code
            dst_city = int(row['dst_city'])  # MaxMind int code
            latency = float(row['latency'])

            if src_ip not in G: add_node(G, speed, src_ip, src_city, src_country)
            if dst_ip not in G: add_node(G, speed, dst_ip, dst_city, dst_country)

            track_latency(latencies, 'ip2ip', src_ip, dst_ip, latency)
            if src_city is not None and dst_city is not None:
                track_latency(latencies, 'city2city', src_city, dst_city, latency)
            track_latency(latencies, 'country2country', src_country, dst_country, latency)
            track_latency(latencies, 'global', 'global', 'global', latency)

    total_edges = len(G) * len(G)
    logging.info("adding {} total edges...".format(total_edges))
    # loop back through to add latencies
    num_completed_edges = 0
    next_step = 0.1
    for s in G:
        for d in G:
            add_edge(G, latencies, s, d)
            num_completed_edges += 1
        if num_completed_edges > total_edges * next_step:
            logging.info("finished {}/{} edges".format(num_completed_edges, total_edges))
            next_step += 0.1

    logging.info("writing graph to {}...".format(OUTGRAPH))
    networkx.write_graphml(G, OUTGRAPH)

def add_edge(G, latencies, s, d):
    if s in latencies['ip2ip'] and d in latencies['ip2ip'][s]:
        latency_list = latencies['ip2ip'][s][d]
    elif d in latencies['ip2ip'] and s in latencies['ip2ip'][d]:
        latency_list = latencies['ip2ip'][d][s]
    elif 'citycode' in G.nodes[s] and 'citycode' in G.nodes[d] and G.nodes[s]['citycode'] in latencies['city2city'] and G.nodes[d]['citycode'] in latencies['city2city'][G.nodes[s]['citycode']]:
        latency_list = latencies['city2city'][G.nodes[s]['citycode']][G.nodes[d]['citycode']]
    elif 'citycode' in G.nodes[d] and 'citycode' in G.nodes[s] and G.nodes[d]['citycode'] in latencies['city2city'] and G.nodes[s]['citycode'] in latencies['city2city'][G.nodes[d]['citycode']]:
        latency_list = latencies['city2city'][G.nodes[d]['citycode']][G.nodes[s]['citycode']]
    elif G.nodes[s]['countrycode'] in latencies['country2country'] and G.nodes[d]['countrycode'] in latencies['country2country'][G.nodes[s]['countrycode']]:
        latency_list = latencies['country2country'][G.nodes[s]['countrycode']][G.nodes[d]['countrycode']]
    elif G.nodes[d]['countrycode'] in latencies['country2country'] and G.nodes[s]['countrycode'] in latencies['country2country'][G.nodes[d]['countrycode']]:
        latency_list = latencies['country2country'][G.nodes[d]['countrycode']][G.nodes[s]['countrycode']]
    else:
        latency_list = latencies['global']['global']['global']

    latency = mean(latency_list)
    assert latency > 0
    if latency > MAX_LATENCY: latency = MAX_LATENCY
    packetloss = latency/MAX_LATENCY*MAX_LOSS

    G.add_edge(s, d, latency=float(latency), packetloss=float(packetloss))

def track_latency(latencies, latency_key, src_key, dst_key, latency):
    if src_key in latencies[latency_key] and dst_key in latencies[latency_key][src_key]:
        latencies[latency_key][src_key][dst_key].append(latency)
    elif dst_key in latencies[latency_key] and src_key in latencies[latency_key][dst_key]:
        latencies[latency_key][dst_key][src_key].append(latency)
    else:
        if src_key in latencies[latency_key]:
            latencies[latency_key][src_key].setdefault(dst_key, []).append(latency)
        elif dst_key in latencies[latency_key]:
            latencies[latency_key][dst_key].setdefault(src_key, []).append(latency)
        else:
            latencies[latency_key].setdefault(src_key, {}).setdefault(dst_key, []).append(latency)

def add_node(G, speed, ip, city, country):
    # prefer city, then country, then fall back to global average
    if city is not None and city in speed['cities']:
        bwup = mbit_to_kib(speed['cities'][city]['up_mbits'])
        bwdown = mbit_to_kib(speed['cities'][city]['down_mbits'])
    elif country in speed['countries']:
        bwup = mbit_to_kib(speed['countries'][country]['up_mbits'])
        bwdown = mbit_to_kib(speed['countries'][country]['down_mbits'])
    else:
        bwup = mbit_to_kib(speed['global_up_mbit'])
        bwdown = mbit_to_kib(speed['global_down_mbit'])

    if city is not None:
        G.add_node(ip, bandwidthdown=int(bwdown), bandwidthup=int(bwup), ip=str(ip), citycode=str(city), countrycode=str(country))
    else:
        G.add_node(ip, bandwidthdown=int(bwdown), bandwidthup=int(bwup), ip=str(ip), countrycode=str(country))
        #G.node[ip]['citycode'] = city

def mbit_to_kib(bw):
    return int(float(bw) * 122.07)

if __name__ == '__main__': main()
