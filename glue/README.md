You've done all the hard work. This **should** just magically work, assuming
input formats haven't changed without this script finding out about it.

The one script is `01-create-atlas.py`.

# Input

For input it takes the final output file from the latency directory and the
final output file from the bandwidth directory, or
`../latency/data/all-pairs.csv` and `../bandwidth/speed-data.json`
respectively.

If you have compressed input data, with a bit of shell magic you don't need to
keep a decompressed copy on disk:

    ./01-create-atlas.py --input-latency <(xzcat all-pairs.csv.xz ) >/dev/null

# Output

By default output from this script is written to stdout. Consider piping
through `xz` if you have a lot of latency data (like an entire full run) as
latency data is directly responsible for the size of the output topology.

    ./01-create-atlas.py | xz > atlas.graphml.xml.xz

The script **does not care** what the `--output` file name is; `-o foo.xz` will
**not** produce compressed output.

# Latency parameters

You can find high latencies on the Internet.

    # 10 highest latency results
    cat ../latency/data/all-pairs.csv | cut -d ',' -f 10 | sort -n | tail

You can use `--max-latency` to cap really high latencies to something smaller.

if you don't want to do that, you still need to set `--max-latency` to the
maximum latency in your input data so that it doesn't cap.

# Packet loss parameters

By default this script generates links with no packet loss, because
`--packetloss-model` defaults to `zero`.

You can alternatively set this parameter to `linear-latency` if you would like
to set packet loss on a link according to the following formula:

    link_packet_loss = link_latency / max_latency * max_packet_loss

The `--max-packetloss` parameter controls the maximum packet loss in this
equation and defaults to 1.5%.
