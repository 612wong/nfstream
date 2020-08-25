#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
------------------------------------------------------------------------------------------------------------------------
tests.py
Copyright (C) 2019-20 - NFStream Developers
This file is part of NFStream, a Flexible Network Data Analysis Framework (https://www.nfstream.org/).
NFStream is free software: you can redistribute it and/or modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later
version.
NFStream is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more details.
You should have received a copy of the GNU Lesser General Public License along with NFStream.
If not, see <http://www.gnu.org/licenses/>.
------------------------------------------------------------------------------------------------------------------------
"""

import unittest
import os
import csv

import numpy as np

from nfstream import NFStreamer, NFPlugin
from nfstream.plugin import bidirectional_packets_matrix


def get_files_list(path):
    files = []
    for r, d, f in os.walk(path):
        for file in f:
            if '.pcap' in file:
                files.append(os.path.join(r, file))
    files.sort()
    return files


def get_app_dict(path):
    with open(path) as csvfile:
        reader = csv.DictReader(csvfile)
        app = {}
        for row in reader:
            try:
                app[row['ndpi_proto']]['bytes'] += int(row['s_to_c_bytes']) + int(row['c_to_s_bytes'])
                app[row['ndpi_proto']]['flows'] += 1
                app[row['ndpi_proto']]['pkts'] += int(row['s_to_c_pkts']) + int(row['c_to_s_pkts'])
            except KeyError:
                app[row['ndpi_proto']] = {"bytes": 0, "flows": 0, "pkts": 0}
                app[row['ndpi_proto']]["bytes"] += int(row['s_to_c_bytes']) + int(row['c_to_s_bytes'])
                app[row['ndpi_proto']]["flows"] += 1
                app[row['ndpi_proto']]['pkts'] += int(row['s_to_c_pkts']) + int(row['c_to_s_pkts'])
    return app


def build_ground_truth_dict(path):
    list_gt = get_files_list(path)
    ground_truth = {}
    for file in list_gt:
        ground_truth[file.split('/')[-1]] = get_app_dict(file)
    return ground_truth


class TestMethods(unittest.TestCase):
    def test_no_unknown_protocols_without_timeouts(self):
        files = get_files_list("tests/pcap/")
        ground_truth_ndpi = build_ground_truth_dict("tests/result/")
        print("\n----------------------------------------------------------------------")
        print(".Testing on {} applications:".format(len(files)))
        ok_files = []
        ko_files = []
        for test_file in files:
            streamer_test = NFStreamer(source=test_file, idle_timeout=31556952, active_timeout=31556952)
            test_case_name = test_file.split('/')[-1]
            result = {}
            for flow in streamer_test:
                if flow.application_name != 'Unknown':
                    try:
                        result[flow.application_name]['bytes'] += flow.bidirectional_raw_bytes
                        result[flow.application_name]['flows'] += 1
                        result[flow.application_name]['pkts'] += flow.bidirectional_packets
                    except KeyError:
                        result[flow.application_name] = {"bytes": flow.bidirectional_raw_bytes,
                                                         'flows': 1, 'pkts': flow.bidirectional_packets}
            if result == ground_truth_ndpi[test_case_name]:
                ok_files.append(test_case_name)
                print("{}\t: \033[94mOK\033[0m".format(test_case_name.ljust(60, ' ')))
            else:
                ko_files.append(test_case_name)
                print(dict(sorted(ground_truth_ndpi[test_case_name].items(), key=lambda x: x[0].lower())))
                print("********************************")
                print(dict(sorted(result.items(),
                                  key=lambda x: x[0].lower())
                           )
                      )
                print("{}\t: \033[31mKO\033[0m".format(test_case_name.ljust(60, ' ')))
        self.assertEqual(len(files), len(ok_files))

    def test_expiration_management(self):
        print("\n----------------------------------------------------------------------")
        streamer_test = NFStreamer(source='tests/pcap/facebook.pcap', active_timeout=0)
        flows = []
        for flow in streamer_test:
            flows.append(flow)
        self.assertEqual(len(flows), 60)
        print("{}\t: \033[94mOK\033[0m".format(".Testing Streamer expiration management".ljust(60, ' ')))

    def test_flow_metadata_extraction(self):
        print("\n----------------------------------------------------------------------")
        streamer_test = NFStreamer(source='tests/pcap/facebook.pcap', bpf_filter="src port 52066 or dst port 52066")
        flows = []
        for flow in streamer_test:
            flows.append(flow)
        del streamer_test
        self.assertEqual(flows[0].client_info, 'facebook.com')
        self.assertEqual(flows[0].server_info, '*.facebook.com,*.facebook.net,*.fb.com,*.fbcdn.net,*.fbsbx.com,\
*.m.facebook.com,*.messenger.com,*.xx.fbcdn.net,*.xy.fbcdn.net,*.xz.fbcdn.net,facebook.com,fb.com,\
messenger.com')
        self.assertEqual(flows[0].client_info, 'facebook.com')
        self.assertEqual(flows[0].ja3_client, 'bfcc1a3891601edb4f137ab7ab25b840')
        self.assertEqual(flows[0].ja3_server, '2d1eb5817ece335c24904f516ad5da12')
        print("{}\t: \033[94mOK\033[0m".format(".Testing metadata extraction".ljust(60, ' ')))

    def test_unfound_device(self):
        print("\n----------------------------------------------------------------------")
        try:
            streamer_test = NFStreamer(source="inexisting_file.pcap")
        except ValueError:
            print("{}\t: \033[94mOK\033[0m".format(".Testing unfoud device".ljust(60, ' ')))

    def test_statistical_features(self):
        print("\n----------------------------------------------------------------------")
        streamer_test = NFStreamer(source='tests/pcap/google_ssl.pcap', statistics=True)
        flows = []
        for flow in streamer_test:
            flows.append(flow)
        del streamer_test
        self.assertEqual(flows[0].id, 0)
        self.assertEqual(flows[0].bidirectional_first_seen_ms, 1434443394683)
        self.assertEqual(flows[0].bidirectional_last_seen_ms, 1434443401353)
        self.assertEqual(flows[0].src2dst_first_seen_ms, 1434443394683)
        self.assertEqual(flows[0].src2dst_last_seen_ms, 1434443401353)
        self.assertEqual(flows[0].dst2src_first_seen_ms, 1434443394717)
        self.assertEqual(flows[0].dst2src_last_seen_ms, 1434443401308)
        self.assertEqual(flows[0].version, 4)
        self.assertEqual(flows[0].src_port, 42835)
        self.assertEqual(flows[0].dst_port, 443)
        self.assertEqual(flows[0].protocol, 6)
        self.assertEqual(flows[0].vlan_id, 0)
        self.assertEqual(flows[0].src_ip, '172.31.3.224')
        self.assertEqual(flows[0].src_ip_type, 1)
        self.assertEqual(flows[0].dst_ip, '216.58.212.100')
        self.assertEqual(flows[0].dst_ip_type, 0)
        self.assertEqual(flows[0].bidirectional_packets, 28)
        self.assertEqual(flows[0].bidirectional_raw_bytes, 9108)
        self.assertEqual(flows[0].bidirectional_ip_bytes, 8696)
        self.assertEqual(flows[0].bidirectional_duration_ms, 6670)
        self.assertEqual(flows[0].src2dst_packets, 16)
        self.assertEqual(flows[0].src2dst_raw_bytes, 1512)
        self.assertEqual(flows[0].src2dst_ip_bytes, 1288)
        self.assertEqual(flows[0].src2dst_duration_ms, 6670)
        self.assertEqual(flows[0].dst2src_packets, 12)
        self.assertEqual(flows[0].dst2src_raw_bytes, 7596)
        self.assertEqual(flows[0].dst2src_ip_bytes, 7408)
        self.assertEqual(flows[0].dst2src_duration_ms, 6591)
        self.assertEqual(flows[0].expiration_id, 0)
        self.assertEqual(flows[0].bidirectional_min_raw_ps, 54)
        self.assertEqual(flows[0].bidirectional_mean_raw_ps, 325.2857142857144)
        self.assertEqual(flows[0].bidirectional_stdev_raw_ps, 500.14981882416123)
        self.assertEqual(flows[0].bidirectional_max_raw_ps, 1484)
        self.assertEqual(flows[0].src2dst_min_raw_ps, 54)
        self.assertEqual(flows[0].src2dst_mean_raw_ps, 94.5)
        self.assertEqual(flows[0].src2dst_stdev_raw_ps, 89.55519713189923)
        self.assertEqual(flows[0].src2dst_max_raw_ps, 368)
        self.assertEqual(flows[0].dst2src_min_raw_ps, 60)
        self.assertEqual(flows[0].dst2src_mean_raw_ps, 632.9999999999999)
        self.assertEqual(flows[0].dst2src_stdev_raw_ps, 649.8457159552985)
        self.assertEqual(flows[0].dst2src_max_raw_ps, 1484)
        self.assertEqual(flows[0].bidirectional_min_ip_ps, 40)
        self.assertEqual(flows[0].bidirectional_mean_ip_ps, 310.57142857142856)
        self.assertEqual(flows[0].bidirectional_stdev_ip_ps, 500.54617788019937)
        self.assertEqual(flows[0].bidirectional_max_ip_ps, 1470)
        self.assertEqual(flows[0].src2dst_min_ip_ps, 40)
        self.assertEqual(flows[0].src2dst_mean_ip_ps, 80.49999999999999)
        self.assertEqual(flows[0].src2dst_stdev_ip_ps, 89.55519713189922)
        self.assertEqual(flows[0].src2dst_max_ip_ps, 354)
        self.assertEqual(flows[0].dst2src_min_ip_ps, 40)
        self.assertEqual(flows[0].dst2src_mean_ip_ps, 617.3333333333334)
        self.assertEqual(flows[0].dst2src_stdev_ip_ps, 651.4524099458397)
        self.assertEqual(flows[0].dst2src_max_ip_ps, 1470)
        self.assertEqual(flows[0].bidirectional_min_piat_ms, 0)
        self.assertEqual(flows[0].bidirectional_mean_piat_ms, 247.037037037037)
        self.assertEqual(flows[0].bidirectional_stdev_piat_ms, 324.04599406227237)
        self.assertEqual(flows[0].bidirectional_max_piat_ms, 995)
        self.assertEqual(flows[0].src2dst_min_piat_ms, 76)
        self.assertEqual(flows[0].src2dst_mean_piat_ms, 444.6666666666667)
        self.assertEqual(flows[0].src2dst_stdev_piat_ms, 398.80726017617934)
        self.assertEqual(flows[0].src2dst_max_piat_ms, 1185)
        self.assertEqual(flows[0].dst2src_min_piat_ms, 66)
        self.assertEqual(flows[0].dst2src_mean_piat_ms, 599.1818181818182)
        self.assertEqual(flows[0].dst2src_stdev_piat_ms, 384.78456782511904)
        self.assertEqual(flows[0].dst2src_max_piat_ms, 1213)
        self.assertEqual(flows[0].master_protocol, 91)
        self.assertEqual(flows[0].app_protocol, 126)
        self.assertEqual(flows[0].application_name, 'TLS.Google')
        self.assertEqual(flows[0].category_name, 'Web')
        self.assertEqual(flows[0].client_info, '')
        self.assertEqual(flows[0].server_info, '')
        self.assertEqual(flows[0].ja3_client, '')
        self.assertEqual(flows[0].ja3_server, '')
        self.assertEqual(flows[0].bidirectional_syn_packets, 2)
        self.assertEqual(flows[0].bidirectional_cwr_packets, 0)
        self.assertEqual(flows[0].bidirectional_ece_packets, 0)
        self.assertEqual(flows[0].bidirectional_urg_packets, 0)
        self.assertEqual(flows[0].bidirectional_ack_packets, 27)
        self.assertEqual(flows[0].bidirectional_psh_packets, 8)
        self.assertEqual(flows[0].bidirectional_rst_packets, 0)
        self.assertEqual(flows[0].bidirectional_fin_packets, 2)
        self.assertEqual(flows[0].src2dst_syn_packets, 1)
        self.assertEqual(flows[0].src2dst_cwr_packets, 0)
        self.assertEqual(flows[0].src2dst_ece_packets, 0)
        self.assertEqual(flows[0].src2dst_urg_packets, 0)
        self.assertEqual(flows[0].src2dst_ack_packets, 15)
        self.assertEqual(flows[0].src2dst_psh_packets, 4)
        self.assertEqual(flows[0].src2dst_rst_packets, 0)
        self.assertEqual(flows[0].src2dst_fin_packets, 1)
        self.assertEqual(flows[0].dst2src_syn_packets, 1)
        self.assertEqual(flows[0].dst2src_cwr_packets, 0)
        self.assertEqual(flows[0].dst2src_ece_packets, 0)
        self.assertEqual(flows[0].dst2src_urg_packets, 0)
        self.assertEqual(flows[0].dst2src_ack_packets, 12)
        self.assertEqual(flows[0].dst2src_psh_packets, 4)
        self.assertEqual(flows[0].dst2src_rst_packets, 0)
        self.assertEqual(flows[0].dst2src_fin_packets, 1)
        print("{}\t: \033[94mOK\033[0m".format(".Testing statistical features".ljust(60, ' ')))

    def test_noroot_live(self):
        print("\n----------------------------------------------------------------------")
        try:
            streamer_test = NFStreamer(source="lo", idle_timeout=0)
        except SystemExit:
            print("{}\t: \033[94mOK\033[0m".format(".Testing live capture (noroot)".ljust(60, ' ')))

    def test_bad_observer_args(self):
        print("\n----------------------------------------------------------------------")

        try:
            streamer_test = NFStreamer(source=1, promisc=53, snaplen="wrong", bpf_filter=False, decode_tunnels=22)
        except ValueError as e:
            self.assertEqual(1, 1)
            print("{}\t: \033[94mOK\033[0m".format(".Testing parameters handling".ljust(60, ' ')))

    def test_user_plugins(self):
        class feat_1(NFPlugin):
            def on_update(self, obs, entry):
                if entry.bidirectional_packets == 4:
                    entry.feat_1 = obs.ip_size

        print("\n----------------------------------------------------------------------")
        streamer_test = NFStreamer(source='tests/pcap/facebook.pcap',
                                   plugins=[feat_1()],
                                   bpf_filter="src port 52066 or dst port 52066")
        rs = []
        for flow in streamer_test:
            rs.append(flow)
        self.assertEqual(rs[0].feat_1, 248)
        self.assertEqual(len(rs), 1)
        del streamer_test
        print("{}\t: \033[94mOK\033[0m".format(".Testing adding user plugins".ljust(60, ' ')))

    def test_custom_expiration(self):
        class custom_expire(NFPlugin):
            def on_update(self, obs, entry):
                if entry.bidirectional_packets == 10:
                    entry.expiration_id = -1
                    entry.custom_expire = True

        print("\n----------------------------------------------------------------------")
        streamer_test = NFStreamer(source='tests/pcap/facebook.pcap',
                                   plugins=[custom_expire(volatile=True)],
                                   bpf_filter="src port 52066 or dst port 52066")
        rs = []
        for flow in streamer_test:
            rs.append(flow)
        self.assertEqual(rs[0].expiration_id, -1)
        self.assertEqual(len(rs), 2)
        del streamer_test
        print("{}\t: \033[94mOK\033[0m".format(".Testing custom expiration".ljust(60, ' ')))

    def test_bpf_filter(self):
        print("\n----------------------------------------------------------------------")
        streamer_test = NFStreamer(source='tests/pcap/facebook.pcap',
                                   statistics=True,
                                   bpf_filter="src port 52066 or dst port 52066")
        count = 0
        for flow in streamer_test:
            print(flow)
            print(flow.to_namedtuple())
            print(flow.to_json())
            count = count + 1
            self.assertEqual(flow.src_port, 52066)
        self.assertEqual(count, 1)
        del streamer_test
        print("{}\t: \033[94mOK\033[0m".format(".Testing BPF filtering".ljust(60, ' ')))

    def test_to_pandas(self):
        print("\n----------------------------------------------------------------------")
        df = NFStreamer(source='tests/pcap/facebook.pcap', statistics=True,
                        bpf_filter="src port 52066 or dst port 52066").to_pandas(ip_anonymization=False)
        self.assertEqual(df["src_port"][0], 52066)
        self.assertEqual(df.shape[0], 1)
        self.assertEqual(df.shape[1], 97)
        print("{}\t: \033[94mOK\033[0m".format(".Testing to Pandas".ljust(60, ' ')))

    def test_to_pandas_anonymized(self):
        print("\n----------------------------------------------------------------------")
        df = NFStreamer(source='tests/pcap/ethereum.pcap',
                        idle_timeout=31556952,
                        active_timeout=31556952).to_pandas(ip_anonymization=True)
        self.assertEqual(df.shape[0], 74)
        self.assertEqual(df.shape[1], 37)
        print("{}\t: \033[94mOK\033[0m".format(".Testing to Pandas ip_anonymization=True".ljust(60, ' ')))

    def test_raw_feature_parsing(self):
        streamer = NFStreamer(
            source='tests/pcap/skype.pcap',
            idle_timeout=60,
            active_timeout=60,
            plugins=[bidirectional_packets_matrix(packet_limit=5)],
            statistics=False
        )

        for entry in streamer:
            assert isinstance(entry.bidirectional_packets_matrix, np.ndarray)
            assert entry.bidirectional_packets_matrix.shape[1] == 6

    def test_raw_feature_parsing_customized(self):
        streamer = NFStreamer(
            source='tests/pcap/skype.pcap',
            idle_timeout=60,
            active_timeout=60,
            plugins=[bidirectional_packets_matrix(packet_limit=5,
                                                  payload_len=False,
                                                  tcp_flag=False,
                                                  ip_proto=False,
                                                  custom_extractors=[
                                                      lambda x: 1,
                                                      lambda x: x.direction,
                                                  ])],
            statistics=False
        )

        for entry in streamer:
            assert isinstance(entry.bidirectional_packets_matrix, np.ndarray)
            # we have 3 mandatory + 2 custom features
            assert entry.bidirectional_packets_matrix.shape[1] == 5
            # this is our constant function
            assert entry.bidirectional_packets_matrix[0, 3] == 1
            # first observation's direction is always 0
            assert entry.bidirectional_packets_matrix[0, 4] == 0


if __name__ == '__main__':
    unittest.main()
