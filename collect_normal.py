import switch_better
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.lib import hub
from datetime import datetime


class CollectTrainingStatsApp(switch_better.SimpleSwitch13):
    def __init__(self, *args, **kwargs):
        super(CollectTrainingStatsApp, self).__init__(*args, **kwargs)

        self.datapaths = {}
        self.monitor_thread = hub.spawn(self.monitor)
        self.total_duration = {}
        self.last_packetin_count = {}
        self.last_flow_stats = {}

        # nagłówek CSV 
        with open("FlowStatsfile_normal.csv", "w") as file0:
            file0.write("dt,switch,src,dst,ip_proto,tp_src,tp_dst,"
                    "pktcount,bytecount,delta_pkts,delta_bytes,"
                    "dpktrate,dbytrate_Bps,byte_per_pkt,"
                    "dur,dur_nsec,tot_dur,flows,packetins,Pairflow,port_no,"
                    "tx_bytes,rx_bytes,tx_kbps,rx_kbps,tot_kbps,label\n")

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]

    def monitor(self):
        while True:
            for dp in self.datapaths.values():
                parser = dp.ofproto_parser

                # zapytanie o FlowStats
                req_flow = parser.OFPFlowStatsRequest(dp)
                dp.send_msg(req_flow)

                # zapytanie o PortStats
                req_port = parser.OFPPortStatsRequest(dp, 0, dp.ofproto.OFPP_ANY)
                dp.send_msg(req_port)

            hub.sleep(3)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        timestamp = datetime.now().timestamp()
        dpid = ev.msg.datapath.id
        body = ev.msg.body

        current_pi = self.packetin_counter
        last_pi = self.last_packetin_count.get(dpid, 0)
        packetins = current_pi - last_pi
        self.last_packetin_count[dpid] = current_pi

        with open("FlowStatsfile_normal.csv", "a+") as file0:
            flows = len([f for f in body if f.priority == 1])

            for stat in [f for f in body if f.priority == 1]:
                m = stat.match
                ip_src = m.get('ipv4_src', '0.0.0.0')
                ip_dst = m.get('ipv4_dst', '0.0.0.0')
                ip_proto = m.get('ip_proto', 0)
                tp_src = m.get('tcp_src', m.get('udp_src', 0))
                tp_dst = m.get('tcp_dst', m.get('udp_dst', 0))

                # Pairflow
                pair = (ip_src, ip_dst)
                reverse_pair = (ip_dst, ip_src)
                Pairflow = 1 if reverse_pair in self.flow_pairs else 0

                # sumowany czas trwania
                self.total_duration[pair] = self.total_duration.get(pair, 0) + stat.duration_sec
                tot_dur = self.total_duration[pair]

                pktcount = stat.packet_count
                bytecount = stat.byte_count
                dur = stat.duration_sec
                dur_nsec = stat.duration_nsec 

                flow_id = (dpid, ip_src, ip_dst, tp_src, tp_dst)
                prev = self.last_flow_stats.get(flow_id, None)
                
                delta_pkts = 0
                delta_bytes = 0
                dpktrate = 0.0
                dbytrate_Bps = 0.0
                byte_per_pkt = 0.0


                if prev:
                    time_diff = timestamp - prev['timestamp']
                    if time_diff > 0:
                        raw_delta_pkts = pktcount - prev['pktcount']
                        raw_delta_bytes = bytecount - prev['bytecount']

                        # zabezpieczenie przed resetem liczników
                        delta_pkts = raw_delta_pkts if raw_delta_pkts > 0 else 0
                        delta_bytes = raw_delta_bytes if raw_delta_bytes > 0 else 0

                        dpktrate = delta_pkts / time_diff
                        dbytrate_Bps = (delta_bytes / time_diff)
                        if delta_pkts > 0:
                            byte_per_pkt = delta_bytes / delta_pkts
                else:
                    # nowy flow
                    delta_pkts = 0
                    delta_bytes = 0

                # zapisanie aktualnego stanu
                self.last_flow_stats[flow_id] = {
                    'timestamp': timestamp,
                    'pktcount': pktcount,
                    'bytecount': bytecount
                }

                # dane z portów
                port_no = -1
                if stat.instructions and hasattr(stat.instructions[0], 'actions'):
                    acts = stat.instructions[0].actions
                    if acts and hasattr(acts[0], 'port'):
                        port_no = acts[0].port

                tx_bytes = rx_bytes = tx_kbps = rx_kbps = tot_kbps = 0
                if dpid in self.port_stats and port_no in self.port_stats[dpid]:
                    p = self.port_stats[dpid][port_no]
                    tx_bytes = p['tx_bytes']
                    rx_bytes = p['rx_bytes']
                    tx_kbps = p['tx_kbps']
                    rx_kbps = p['rx_kbps']
                    tot_kbps = tx_kbps + rx_kbps

                # zapis do pliku
                file0.write("{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
                        timestamp, dpid, ip_src, ip_dst, ip_proto, tp_src, tp_dst,
                        pktcount, bytecount, delta_pkts, delta_bytes,
                        dpktrate, dbytrate_Bps, byte_per_pkt,
                        dur, dur_nsec, tot_dur, flows,
                        packetins, Pairflow, port_no,
                        tx_bytes, rx_bytes, tx_kbps, rx_kbps, tot_kbps, 0))

