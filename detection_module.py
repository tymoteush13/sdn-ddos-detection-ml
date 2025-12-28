from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
)
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, ether_types
from ryu.lib.packet import ipv4, icmp, tcp, udp, arp
from ryu.lib import hub

import pandas as pd
import numpy as np
import joblib
import time
import os
from datetime import datetime


class MitigationSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # ścieżka do wytrenowanego modelu
    MODEL_PATH = "/home/tymek/Desktop/project/data/xgboost.pkl"
    ANALYSIS_INTERVAL = 3  # co ile sekund wywołanie ML

    def __init__(self, *args, **kwargs):
        super(MitigationSwitch13, self).__init__(*args, **kwargs)

        # --- klasyczny switch learningowy ---
        self.mac_to_port = {}
        self.flow_pairs = {}
        self.packetin_counter = 0
        self.port_stats = {}
        self.datapaths = {}

        # Statystyki TCP pomocne przy identyfikacji SYN flood
        self.tcp_syn_count = {}
        self.tcp_synack_count = {}

        self.ip_to_mac = {}
        self.arp_ip_to_mac = {}

        # --- stan do ML / monitoringu ---
        self.flow_records = []
        self.last_flow_stats = {}
        self.last_packetin_count = {}

        # --- ładowanie modelu ---
        if os.path.exists(self.MODEL_PATH):
            self.model = joblib.load(self.MODEL_PATH)
            self.logger.info(f"[ML] Załadowano model z {self.MODEL_PATH}")
        else:
            self.model = None
            self.logger.error(f"[ML] Brak modelu: {self.MODEL_PATH}")

        # --- wątki ---
        self.monitor_thread = hub.spawn(self._monitor)
        self.analysis_thread = hub.spawn(self._analysis_loop)

    # ------------------------------------------------------------------
    # Instalacja reguły table-miss (wszystko nieznane → do kontrolera)
    # ------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(
            ofproto.OFPP_CONTROLLER,
            ofproto.OFPCML_NO_BUFFER
        )]
        self.add_flow(datapath, 0, match, actions)

    # ------------------------------------------------------------------
    # Dodawanie reguły do flow table
    # ------------------------------------------------------------------
    def add_flow(self, datapath, priority, match, actions,
                 buffer_id=None, idle=0, hard=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(
                datapath=datapath, buffer_id=buffer_id,
                priority=priority, match=match,
                idle_timeout=idle, hard_timeout=hard,
                instructions=inst
            )
        else:
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority, match=match,
                idle_timeout=idle, hard_timeout=hard,
                instructions=inst
            )
        datapath.send_msg(mod)

    # ------------------------------------------------------------------
    # rejestracja / usuwanie datapathów
    # ------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]

    # ------------------------------------------------------------------
    # PacketIn → learning MAC, IP, par flowów
    # ------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        self.packetin_counter += 1

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        # ARP → IP→MAC
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            self.arp_ip_to_mac[arp_pkt.src_ip] = src

        # learning MAC → port
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        # IPv4 → IP→MAC + flow_pairs
        ip = pkt.get_protocol(ipv4.ipv4)
        if ip:
            self.ip_to_mac[ip.src] = src
            pair = (ip.src, ip.dst)
            self.flow_pairs[pair] = self.flow_pairs.get(pair, 0) + 1

        # wybór portu wyjściowego
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Instalacja prostej reguły flow jeśli wiemy gdzie iść
        if out_port != ofproto.OFPP_FLOOD and eth.ethertype == ether_types.ETH_TYPE_IP:
            protocol = ip.proto
            # Tworzenie matchów pod protokoły
            if protocol == 1:  # ICMP
                t = pkt.get_protocol(icmp.icmp)
                match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_IP,
                    ipv4_src=ip.src, ipv4_dst=ip.dst,
                    ip_proto=protocol,
                    icmpv4_code=t.code, icmpv4_type=t.type
                )
            elif protocol == 6:  # TCP
                t = pkt.get_protocol(tcp.tcp)
                tcp_flags = t.bits

                src_ip = ip.src
                # Zbieranie statystyk TCP SYN / SYN-ACK
                if (tcp_flags & 0x02) and not (tcp_flags & 0x10):
                    self.tcp_syn_count[src_ip] = self.tcp_syn_count.get(src_ip, 0) + 1
                if (tcp_flags & 0x02) and (tcp_flags & 0x10):
                    self.tcp_synack_count[src_ip] = self.tcp_synack_count.get(src_ip, 0) + 1

                match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_IP,
                    ipv4_src=ip.src, ipv4_dst=ip.dst,
                    ip_proto=protocol,
                    tcp_src=t.src_port, tcp_dst=t.dst_port
                )
            elif protocol == 17:  # UDP
                u = pkt.get_protocol(udp.udp)
                match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_IP,
                    ipv4_src=ip.src, ipv4_dst=ip.dst,
                    ip_proto=protocol,
                    udp_src=u.src_port, udp_dst=u.dst_port
                )
            else:
                match = None
            # Instalacja reguły
            if match is not None:
                if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                    self.add_flow(datapath, 1, match, actions,
                                  msg.buffer_id, idle=20, hard=100)
                    return
                else:
                    self.add_flow(datapath, 1, match, actions,
                                  idle=20, hard=100)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=data
        )
        datapath.send_msg(out)

    # ------------------------------------------------------------------
    # PortStatsReply → aktualizacja port_stats
    # ------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        dpid = ev.msg.datapath.id
        now = datetime.now().timestamp()
        self.port_stats.setdefault(dpid, {})

        for stat in ev.msg.body:
            port_no = stat.port_no
            tx_bytes = stat.tx_bytes
            rx_bytes = stat.rx_bytes

            prev = self.port_stats[dpid].get(port_no, None)
            if prev:
                time_diff = now - prev['timestamp']
                tx_kbps = (8 * (tx_bytes - prev['tx_bytes']) / 1000.0) / time_diff if time_diff > 0 else 0
                rx_kbps = (8 * (rx_bytes - prev['rx_bytes']) / 1000.0) / time_diff if time_diff > 0 else 0
            else:
                tx_kbps = rx_kbps = 0

            self.port_stats[dpid][port_no] = {
                'timestamp': now,
                'tx_bytes': tx_bytes,
                'rx_bytes': rx_bytes,
                'tx_kbps': tx_kbps,
                'rx_kbps': rx_kbps
            }

    # ------------------------------------------------------------------
    # monitor → cykliczne pobieranie FlowStats i PortStats
    # ------------------------------------------------------------------
    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                parser = dp.ofproto_parser
                dp.send_msg(parser.OFPFlowStatsRequest(dp))
                dp.send_msg(parser.OFPPortStatsRequest(
                    dp, 0, dp.ofproto.OFPP_ANY))
            hub.sleep(1)

    # ------------------------------------------------------------------
    # odbiór FlowStatsReply → budowa cech do ML
    # ------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        ts = time.time()
        dpid = ev.msg.datapath.id
        body = ev.msg.body

        current_pi = self.packetin_counter
        last_pi = self.last_packetin_count.get(dpid, 0)
        packetins = current_pi - last_pi
        self.last_packetin_count[dpid] = current_pi

        flows = len([f for f in body if f.priority == 1])

        for stat in [f for f in body if f.priority == 1]:
            m = stat.match
            ip_src = m.get("ipv4_src", "0.0.0.0")
            ip_dst = m.get("ipv4_dst", "0.0.0.0")
            ip_proto = m.get("ip_proto", 0)

            # ICMP — tylko echo request
            if ip_proto == 1:
                icmp_type = m.get("icmpv4_type", None)
                if icmp_type is not None and icmp_type != 8:
                    continue

            tp_src = m.get("tcp_src", m.get("udp_src", 0))
            tp_dst = m.get("tcp_dst", m.get("udp_dst", 0))

            pair = (ip_src, ip_dst)
            reverse_pair = (ip_dst, ip_src)
            Pairflow = 1 if reverse_pair in self.flow_pairs else 0

            pktcount = stat.packet_count
            bytecount = stat.byte_count
            dur = stat.duration_sec
            dur_nsec = stat.duration_nsec

            flow_id = (dpid, ip_src, ip_dst, tp_src, tp_dst)
            prev = self.last_flow_stats.get(flow_id, None)

            delta_pkts = delta_bytes = 0
            dpktrate = dbytrate_Bps = byte_per_pkt = 0

            if prev:
                dt = ts - prev["timestamp"]
                if dt > 0:
                    delta_pkts = max(0, pktcount - prev["pktcount"])
                    delta_bytes = max(0, bytecount - prev["bytecount"])
                    dpktrate = delta_pkts / dt
                    dbytrate_Bps = delta_bytes / dt
                    byte_per_pkt = (delta_bytes / delta_pkts) if delta_pkts > 0 else 0

            self.last_flow_stats[flow_id] = {
                "timestamp": ts,
                "pktcount": pktcount,
                "bytecount": bytecount
            }

            # przepływność portu
            port_no = -1
            if stat.instructions and hasattr(stat.instructions[0], "actions"):
                acts = stat.instructions[0].actions
                if acts and hasattr(acts[0], "port"):
                    port_no = acts[0].port

            tx_bytes = rx_bytes = tx_kbps = rx_kbps = tot_kbps = 0
            if dpid in self.port_stats and port_no in self.port_stats[dpid]:
                p = self.port_stats[dpid][port_no]
                tx_bytes = p["tx_bytes"]
                rx_bytes = p["rx_bytes"]
                tx_kbps = p["tx_kbps"]
                rx_kbps = p["rx_kbps"]
                tot_kbps = tx_kbps + rx_kbps

            self.flow_records.append([
                dpid, ip_src, ip_dst, ip_proto, tp_src, tp_dst,
                pktcount, bytecount,
                delta_pkts, delta_bytes, dpktrate, dbytrate_Bps, byte_per_pkt,
                dur, dur_nsec, dur, flows, packetins, Pairflow, port_no,
                tx_bytes, rx_bytes, tx_kbps, rx_kbps, tot_kbps
            ])

    # ------------------------------------------------------------------
    # główna pętla ML + blokowanie
    # ------------------------------------------------------------------
    def _analysis_loop(self):
        model_features = [
            "tp_src", "tp_dst",
            "pktcount", "bytecount",
            "delta_pkts", "delta_bytes",
            "dpktrate", "dbytrate_Bps", "byte_per_pkt",
            "dur",
            "packetins",
            "tx_bytes", "rx_bytes", "tx_kbps", "rx_kbps", "tot_kbps"
        ]

        DECISION_THRESHOLD = 0.60

        while True:
            hub.sleep(self.ANALYSIS_INTERVAL)

            if not self.flow_records or self.model is None:
                continue
            # Tworzenie DataFrame dla modelu ML
            df = pd.DataFrame(self.flow_records, columns=[
                "switch", "ip_src", "ip_dst", "ip_proto", "tp_src", "tp_dst",
                "pktcount", "bytecount",
                "delta_pkts", "delta_bytes", "dpktrate", "dbytrate_Bps", "byte_per_pkt",
                "dur", "dur_nsec", "tot_dur", "flows",
                "packetins", "Pairflow", "port_no",
                "tx_bytes", "rx_bytes", "tx_kbps", "rx_kbps", "tot_kbps"
            ])

            df = df.drop(columns=[
                "switch", "ip_proto", "dur_nsec", "tot_dur", "flows", "Pairflow", "port_no"
            ], errors="ignore")

            log_cols = [
                "pktcount", "bytecount", "delta_pkts", "delta_bytes",
                "dpktrate", "dbytrate_Bps", "byte_per_pkt",
                "tx_bytes", "rx_bytes", "tx_kbps", "rx_kbps", "tot_kbps"
            ]
            for col in log_cols:
                if col in df.columns:
                    df[col] = np.log1p(df[col])

            df = df.replace([np.inf, -np.inf], 0).fillna(0)

            zero_mask = (
                (df["delta_pkts"] == 0) &
                (df["delta_bytes"] == 0) &
                (df["dpktrate"] == 0) &
                (df["dbytrate_Bps"] == 0) &
                (df["byte_per_pkt"] == 0)
            )
            df = df[~zero_mask]

            if df.empty:
                self.flow_records.clear()
                continue

            df = df.reindex(columns=model_features, fill_value=0)

            preds = self.model.predict(df)
            total = len(preds)
            attacks = int(preds.sum())
            normals = total - attacks
            ratio = attacks / total if total > 0 else 0

            ts = datetime.now().strftime("%H:%M:%S")
            self.logger.info(
                f"[DDoS] {ts} | batch={total} | normal={normals} | atak={attacks} | udział={ratio*100:.2f}%"
            )

            if attacks >= 5 or ratio >= 0.20:
                self.logger.warning(f"[DDoS] WYKRYTO ATAK")

                # bierzemy TYLKO flowy oznaczone jako atak (pred=1)
                attack_indices = df.index[preds == 1]

                if len(attack_indices) == 0:
                    self.logger.error("[DDoS] Błąd: warunek wykrycia ataku spełniony, ale brak attack_indices!")
                    self.flow_records.clear()
                    continue

                # szukamy flow o największym dpktrate spośród flowów atakujących
                worst_flow_idx = df.loc[attack_indices]["dpktrate"].idxmax()

                src = self.flow_records[worst_flow_idx][1]
                dst = self.flow_records[worst_flow_idx][2]
                dpid = int(self.flow_records[worst_flow_idx][0])

                # LAND atak (źródło == cel) — spoofing IP
                if src == dst:
                    attacker_ip = src
                    attacker_mac = self.ip_to_mac.get(attacker_ip) or self.arp_ip_to_mac.get(attacker_ip)
                    self.logger.error(
                        f"[LAND] Wykryto atak LAND z {attacker_ip} "
                        f"(MAC {attacker_mac})"
                    )
                    self.flow_records.clear()
                    continue


                # Filtrowanie TCP
                attacker_ip = None
                victim_ip = None

                # Na podstawie stosunku SYN / SYN-ACK ustalenie kto jest ofiara a kto atakuje
                for ip_addr, syn_count in self.tcp_syn_count.items():
                    synack = self.tcp_synack_count.get(ip_addr, 0)
                    if syn_count > 10 and synack < 2:
                        attacker_ip = ip_addr

                for ip_addr, synack_count in self.tcp_synack_count.items():
                    syns = self.tcp_syn_count.get(ip_addr, 0)
                    if synack_count > 5 and syns < 2:
                        victim_ip = ip_addr

                if attacker_ip is None:
                    attacker_ip = src
                if victim_ip is None:
                    victim_ip = dst

                attacker_mac = self.arp_ip_to_mac.get(attacker_ip)
                victim_mac = self.arp_ip_to_mac.get(victim_ip)
                in_port = None

                if attacker_mac:
                    if dpid in self.mac_to_port:
                        if attacker_mac in self.mac_to_port[dpid]:
                            in_port = self.mac_to_port[dpid][attacker_mac]

                self.logger.error(
                    f"[ALERT] OFIARA: {victim_ip} jest atakowana przez {attacker_ip} "
                    f"(MAC atakującego: {attacker_mac}, MAC ofiary: {victim_mac}"
                )