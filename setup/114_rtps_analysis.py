#!/usr/bin/env python3
"""Decode this probe's SLL2 IPv4 pcap, retaining IP fragment evidence.

Port-only BPF misses noninitial fragments. Never interpret a partial UDP
datagram as proof that later RTPS samples were not sent.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import socket
import struct


def read_pcap(path):
    blob = path.read_bytes()
    if blob[:4] != b'\xd4\xc3\xb2\xa1':
        raise ValueError('Expected little-endian microsecond pcap')
    if struct.unpack_from('<I', blob, 20)[0] != 276:
        raise ValueError('Expected tcpdump Linux SLL2 capture')
    records, offset = [], 24
    while offset < len(blob):
        sec, usec, size, _ = struct.unpack_from('<IIII', blob, offset)
        record = blob[offset:offset + 16 + size]
        packet = record[16:]
        offset += len(record)
        if packet[:2] != b'\x08\x00':
            continue
        ip = packet[20:]
        if len(ip) < 20 or ip[9] != 17:
            continue
        ihl = (ip[0] & 15) * 4
        total, ident, frag = struct.unpack_from('!HHH', ip, 2)
        records.append(dict(wall_ns=(sec * 1_000_000 + usec) * 1000,
            source=socket.inet_ntoa(ip[12:16]), destination=socket.inet_ntoa(ip[16:20]),
            ident=ident, offset=(frag & 8191) * 8, more=bool(frag & 8192),
            interface=struct.unpack_from('!I', packet, 4)[0], packet_type=packet[10],
            payload=ip[ihl:total], record=record))
    return blob[:24], records


def decode_udp(row, payload):
    source_port, destination_port, length, _ = struct.unpack_from('!HHHH', payload)
    if len(payload) != length:
        raise ValueError('Refuse partial UDP datagram')
    rtps = payload[8:]
    if rtps[:4] != b'RTPS':
        return []
    prefix = rtps[8:20].hex()
    result, offset, destination_prefix = [], 20, None
    while offset + 4 <= len(rtps):
        kind, flags = rtps[offset:offset + 2]
        endian = '<' if flags & 1 else '>'
        length = struct.unpack_from(endian + 'H', rtps, offset + 2)[0]
        end = offset + 4 + length if length else len(rtps)
        if end > len(rtps):
            raise ValueError('Truncated RTPS submessage')
        body = rtps[offset + 4:end]
        if kind == 14:
            destination_prefix = body[:12].hex()
        msg = dict(wall_ns=row['wall_ns'], guid=prefix, destination_guid=destination_prefix,
            source_port=source_port, destination_port=destination_port, kind=kind)

        def seq(at):
            hi, lo = struct.unpack_from(endian + 'iI', body, at)
            return hi * 2**32 + lo

        if kind in (6, 7) and len(body) >= 20:
            msg.update(reader=body[:4].hex(), writer=body[4:8].hex())
            if kind == 7 and len(body) >= 28:
                msg.update(first=seq(8), last=seq(16), count=struct.unpack_from(endian + 'I', body, 24)[0])
            elif kind == 6:
                bits = struct.unpack_from(endian + 'I', body, 16)[0]
                words = [struct.unpack_from(endian + 'I', body, at)[0]
                         for at in range(20, 20 + 4 * ((bits + 31)//32), 4)]
                missing = [seq(8) + bit for bit in range(bits)
                           if words[bit//32] & (1 << (31 - bit % 32))]
                msg.update(base=seq(8), bits=bits, missing=missing)
            result.append(msg)
        elif kind == 21 and len(body) >= 20:
            msg.update(writer=body[8:12].hex(), sequence=seq(12))
            pos = 4 + struct.unpack_from(endian + 'H', body, 2)[0]
            if flags & 2:  # inline QoS parameter list
                while pos + 4 <= len(body):
                    pid, size = struct.unpack_from(endian + 'HH', body, pos)
                    pos += 4 + size
                    if pid == 1:
                        break
            pos += 4  # serialized payload encapsulation
            if msg['writer'] in ('000003c2', '000004c2'):
                while pos + 4 <= len(body):
                    pid, size = struct.unpack_from(endian + 'HH', body, pos)
                    value = body[pos + 4:pos + 4 + size]
                    if pid == 5 and len(value) >= 4:
                        n = struct.unpack_from(endian + 'I', value)[0]
                        msg['topic'] = value[4:4 + n].rstrip(b'\0').decode(errors='replace')
                    pos += 4 + size
                    if pid == 1:
                        break
            result.append(msg)
        offset = end
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pcap', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--filtered-pcap', type=Path)
    ap.add_argument('--port-min', type=int, default=47150)
    ap.add_argument('--port-max', type=int, default=47250)
    args = ap.parse_args()
    header, records = read_pcap(args.pcap)
    groups, selected, messages, fragment_rows = {}, [], [], []

    def probe_ports(payload):
        src, dst = struct.unpack_from('!HH', payload)
        return args.port_min <= src <= args.port_max or args.port_min <= dst <= args.port_max

    for row in records:
        if row['more'] or row['offset']:
            key = (row['source'], row['destination'], row['ident'])
            groups.setdefault(key, []).append(row)
        elif len(row['payload']) >= 8 and probe_ports(row['payload']):
            selected.append(row)
            messages.extend(decode_udp(row, row['payload']))
    for key, rows in groups.items():
        first = next((r for r in rows if not r['offset']), None)
        if first is None or not probe_ports(first['payload']):
            continue
        selected.extend(rows)
        chunks = {r['offset']: r['payload'] for r in rows}
        length = struct.unpack_from('!H', first['payload'], 4)[0]
        payload = bytearray(length)
        covered = bytearray(length)
        for offset, chunk in chunks.items():
            stop = min(length, offset + len(chunk))
            payload[offset:stop] = chunk[:stop-offset]
            covered[offset:stop] = b'\x01' * (stop-offset)
        complete = all(covered) and any(not r['more'] for r in rows)
        direction_coverage = {}
        for packet_type in sorted(set(r['packet_type'] for r in rows)):
            matching = [r for r in rows if r['packet_type'] == packet_type]
            offsets = sorted(set(r['offset'] for r in matching))
            present = bytearray(length)
            for r in matching:
                start, stop = r['offset'], min(length, r['offset'] + len(r['payload']))
                present[start:stop] = b'\x01' * (stop-start)
            direction_coverage[str(packet_type)] = dict(offsets=offsets, bytes=sum(present),
                complete=all(present) and any(not r['more'] for r in matching))
        fragment_rows.append(dict(source=key[0], destination=key[1], ip_id=key[2],
            wall_ns=min(r['wall_ns'] for r in rows), udp_length=length,
            captured_offsets=sorted(chunks), captured_bytes=sum(covered), complete=complete,
            interfaces=sorted(set(r['interface'] for r in rows)),
            packet_types=sorted(set(r['packet_type'] for r in rows)), copies=len(rows),
            direction_coverage=direction_coverage))
        if complete:
            messages.extend(decode_udp(first, payload))
    args.out.mkdir(parents=True, exist_ok=True)
    summary = dict(selected_frame_copies=len(selected), fragment_datagrams=len(fragment_rows),
        complete_fragment_datagrams=sum(r['complete'] for r in fragment_rows),
        incomplete_fragment_datagrams=sum(not r['complete'] for r in fragment_rows),
        interface_packet_types=dict(Counter(f"{r['interface']}:{r['packet_type']}" for r in selected)),
        caveat='Frame copies are not independent samples; capture completeness does not prove socket delivery.',
        fragments=fragment_rows)
    (args.out / 'fragment_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (args.out / 'rtps_messages.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in messages))
    if args.filtered_pcap:
        selected.sort(key=lambda r:r['wall_ns'])
        args.filtered_pcap.write_bytes(header+b''.join(r['record'] for r in selected))
    print(json.dumps({k:v for k,v in summary.items() if k != 'fragments'}))


if __name__ == '__main__':
    main()
