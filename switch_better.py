from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types

from ryu.lib.packet import in_proto
from ryu.lib.packet import ipv4
from ryu.lib.packet import icmp
from ryu.lib.packet import tcp
from ryu.lib.packet import udp
from ryu.lib.packet import arp
from datetime import datetime

class SimpleSwitch13(app_manager.RyuApp):
    # Kontroler pracuje w standardzie OpenFlow 1.3
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.flow_pairs = {}           # (src, dst) → liczba flowów
        self.packetin_counter = 0      # licznik PacketIn
        self.port_stats = {}           # statystyki portów
        self.datapaths = {}            # zarejestrowane datapathy

        self.mitigation = 0
        self.blocked_ports = {}
        self.ip_to_mac = {}
        self.blocked_hosts = set()
        self.arp_ip_to_mac = {}


    # -------------------------------------------------------------------------
    # Funkcja wywoływana po nawiązaniu połączenia kontrolera z przełącznikiem
    # Dodaje podstawową regułę przekazującą nieznane pakiety do kontrolera.
    # -------------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)


    # -------------------------------------------------------------------------
    # Funkcja pomocnicza do dodawania przepływów (flow entries) w przełączniku.
    # Tworzy regułę OpenFlow z określonym priorytetem, dopasowaniem i akcjami.
    # -------------------------------------------------------------------------
    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle=0, hard=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    idle_timeout=idle, hard_timeout=hard,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    idle_timeout=idle, hard_timeout=hard,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)


    # -------------------------------------------------------------------------
    # Obsługuje zmiany stanu przełączników (podłączanie / odłączanie).
    # Aktualizuje listę aktywnych datapathów w kontrolerze Ryu.
    # -------------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]

    # -------------------------------------------------------------------------
    # Obsługuje odpowiedzi PortStatsReply z przełącznika.
    # Na ich podstawie oblicza chwilowe przepływności (tx/rx_kbps) dla portów.
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Obsługuje zdarzenia PacketIn — pakiety wysyłane z przełącznika do kontrolera.
    # Umożliwia naukę tablicy MAC (MAC learning) i dynamiczne instalowanie flowów.
    # -------------------------------------------------------------------------
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

        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            self.arp_ip_to_mac[arp_pkt.src_ip] = src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port


        # Zapamiętywanie mapowania IP → MAC
        ip = pkt.get_protocol(ipv4.ipv4)
        if ip:
            self.ip_to_mac[ip.src] = src


        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Obsługa pakietów IPv4 – budowanie dopasowań dla flowów
        if out_port != ofproto.OFPP_FLOOD and eth.ethertype == ether_types.ETH_TYPE_IP:
            ip = pkt.get_protocol(ipv4.ipv4)
            srcip = ip.src
            dstip = ip.dst
            protocol = ip.proto

            pair = (srcip, dstip)
            self.flow_pairs[pair] = self.flow_pairs.get(pair, 0) + 1

            # Tworzenie dopasowania dla konkretnego protokołu
            if protocol == in_proto.IPPROTO_ICMP:
                t = pkt.get_protocol(icmp.icmp)
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                        ipv4_src=srcip, ipv4_dst=dstip,
                                        ip_proto=protocol,
                                        icmpv4_code=t.code, icmpv4_type=t.type)
            elif protocol == in_proto.IPPROTO_TCP:
                t = pkt.get_protocol(tcp.tcp)
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                        ipv4_src=srcip, ipv4_dst=dstip,
                                        ip_proto=protocol,
                                        tcp_src=t.src_port, tcp_dst=t.dst_port)
            elif protocol == in_proto.IPPROTO_UDP:
                u = pkt.get_protocol(udp.udp)
                match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,
                                        ipv4_src=srcip, ipv4_dst=dstip,
                                        ip_proto=protocol,
                                        udp_src=u.src_port, udp_dst=u.dst_port)
            else:
                return

            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id, idle=20, hard=100)
                return
            else:
                self.add_flow(datapath, 1, match, actions, idle=20, hard=100)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)


    def block_port(self, datapath, portnumber):
        dpid = datapath.id
        self.blocked_ports.setdefault(dpid, set())

        if portnumber in self.blocked_ports[dpid]:
            return

        # Jeśli pierwszy raz blokujemy:
        self.blocked_ports[dpid].add(portnumber)

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(in_port=portnumber)
        actions = []   # DROP
        self.add_flow(datapath, 200, match, actions, idle=60, hard=120)

        self.logger.warning(f" Zablokowano port {portnumber} na przełączniku {dpid}")