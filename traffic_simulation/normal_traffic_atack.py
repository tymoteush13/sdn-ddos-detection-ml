from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSKernelSwitch, RemoteController
import time
import random
from datetime import datetime
import csv

class MyTopo (Topo):
    def build(self):

        s1 = self.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s3 = self.addSwitch('s3', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s4 = self.addSwitch('s4', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s5 = self.addSwitch('s5', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s6 = self.addSwitch('s6', cls=OVSKernelSwitch, protocols='OpenFlow13')

        hosts = []
        for i in range(1, 21):
            h = self.addHost(
                f'h{i}',
                mac=f'00:00:00:00:00:{i:02d}',
                ip=f'10.0.0.{i}/24'
            )
            hosts.append(h)


        self.addLink(hosts[0],s1)
        self.addLink(hosts[1],s1)
        self.addLink(hosts[2],s1)
        self.addLink(hosts[3],s1)

        self.addLink(hosts[4],s2)
        self.addLink(hosts[5],s2)
        self.addLink(hosts[6],s2)

        self.addLink(hosts[7],s3)

        self.addLink(hosts[8],s4)
        self.addLink(hosts[9],s4)
        self.addLink(hosts[10],s4)

        self.addLink(hosts[11],s5)
        self.addLink(hosts[12],s5)
        self.addLink(hosts[13],s5)

        self.addLink(hosts[14],s6)
        self.addLink(hosts[15],s6)
        self.addLink(hosts[16],s6)
        self.addLink(hosts[17],s6)

        self.addLink(s1,s2)
        self.addLink(s2,s3)
        self.addLink(s3,s4)
        self.addLink(s3,s5)
        self.addLink(s5,s6)

        self.addLink(hosts[18], s5)
        self.addLink(hosts[19], s1)

def start_network():
    topo = MyTopo()
    c0 = RemoteController('c0', ip='127.0.0.1', port=6653)
    net = Mininet(topo=topo, controller=c0, link=TCLink)

    net.start()

    hosts = [net.get(f'h{i}') for i in range(1, 21)]
    h8 = net.get('h8')  # host z serwerem HTTP i iperf

    print("Generating traffic ...")

    WEB_DIR = '/home/tymek/Desktop/project/mininet_web'
    HTTP_PORT = 8080
    IPERF_TCP_PORT = 5050
    IPERF_UDP_PORT = 5051

    # uruchomienie serwerów
    h8.cmd(f'python3 -m http.server {HTTP_PORT} --directory {WEB_DIR} &')
    h8.cmd(f'iperf -s -p {IPERF_TCP_PORT} &')
    h8.cmd(f'iperf -s -u -p {IPERF_UDP_PORT} &')

    print("HTTP server started on h8, serving files from:", WEB_DIR)
    print(f"Access it at: http://{h8.IP()}:{HTTP_PORT}/")
    print(f"iperf TCP server running on port {IPERF_TCP_PORT}")
    print(f"iperf UDP server running on port {IPERF_UDP_PORT}")
    time.sleep(2)

    DOWNLOAD_DIR = '/home/tymek/Downloads'
    TARGET_IP = hosts[7].IP()  # IP h8, czyli host z serwerem

    for h in hosts:
        h.cmd(f'mkdir -p {DOWNLOAD_DIR}')
        h.cmd(f'cd {DOWNLOAD_DIR}')

    # Plik logów
    LOG_FILE = "traffic_log.csv"
    # Nagłówek CSV
    with open(LOG_FILE, "w", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "iteration", "step", "traffic_type",
            "src_name", "src_ip", "dst_ip", "target_ip",
            "icmp_count", "tcp_parallel", "udp_bandwidth", "iperf_time",
            "packet_size", "pause_time", "command"
        ])

    # Liczba kolek
    NUM_ITERATIONS = 1
    # liczba wykonan w 1 iteracji
    NUM_TRAFFIC = 1

    start_traffic = datetime.now()

    for i in range(NUM_ITERATIONS):
        print("================================================================================")
        print(f"Iteration n {i+1} ...")
        print("================================================================================")


        for j in range(NUM_TRAFFIC):
            src = random.choice(hosts)
            dst = random.choice([h for h in hosts if h != src])
            dst_ip = dst.IP()

            # --- LOSOWE PARAMETRY --- #
            udp_bandwidth = random.choice(['100K', '500K', '2M', '10M'])  # Limity przepustowosci
            tcp_parallel = random.randint(1, 2)  # liczba strumieni TCP
            pause_time = random.randint(10, 15)   # sekundy przerwy
            icmp_count = random.randint(10, 25)
            iperf_time = random.randint(10, 15)
            wget_rate = random.choice(['50k', '200k', '1m', '5m'])

            traffic_types = ["ICMP", "TCP", "UDP", "HTTP"]
            random.shuffle(traffic_types)

            print(f"\n[{src.name}] Randomized traffic order: {traffic_types}")


            for step_idx, t_type in enumerate(traffic_types, start=1):
                cmd = ""
                if t_type == "ICMP":
                    cmd = f"ping {dst_ip} -c {icmp_count}"
                    print(f"[ICMP] {src.name} → {dst_ip}")
                elif t_type == "TCP":
                    print(f"[TCP] {src.name} → {TARGET_IP}, {tcp_parallel} parallel streams")
                    cmd = f"timeout {iperf_time} iperf -p {IPERF_TCP_PORT} -P {tcp_parallel} -c {TARGET_IP}"
                elif t_type == "UDP":
                    print(f"[UDP] {src.name} → {TARGET_IP}, bandwidth={udp_bandwidth}")
                    cmd = f"timeout {iperf_time} iperf -u -p {IPERF_UDP_PORT} -b {udp_bandwidth} -c {TARGET_IP}"
                elif t_type == "HTTP":
                    print(f"[HTTP] {src.name} downloading test.zip from h8 ({TARGET_IP})")
                    cmd = f"wget -q --limit-rate={wget_rate} http://{TARGET_IP}:{HTTP_PORT}/test.zip -P {DOWNLOAD_DIR}"


                    with open(LOG_FILE, "a", newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow([
                            i+1, step_idx, "HTTP_testzip",
                            src.name, src.IP(), dst_ip, TARGET_IP,
                            "", "", "", "", "", pause_time, cmd
                        ])

                    src.cmd(cmd)
                    time.sleep(4)
                    continue

                with open(LOG_FILE, "a", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([
                        i+1, step_idx, t_type,
                        src.name, src.IP(), dst_ip, TARGET_IP,
                        icmp_count if t_type == "ICMP" else "",
                        tcp_parallel if t_type == "TCP" else "",
                        udp_bandwidth if t_type == "UDP" else "",
                        iperf_time if t_type in ("TCP","UDP") else "",
                        "", pause_time, cmd
                    ])

                try:
                    src.cmd(cmd)
                except Exception as e:
                    # nie przerywanie symulacji jeśli pojedyncza komenda się nie uda
                    print(f"Warning: command failed: {cmd}, error: {e}")

                time.sleep(random.uniform(1,3))

            time.sleep(pause_time)

        print(f"Sleeping 5s before next traffic...")
        time.sleep(5)

    end_traffic = datetime.now()

    print(f"Attack phase duration: {end_traffic - start_traffic}")

    print(f"All traffic completed")

    print("\n================================================================================")
    print(" Starting attack phase ")
    print("================================================================================")

    src = random.choice(hosts)
    dst = random.choice([h for h in hosts if h != src])
    dst_ip = dst.IP()
    print(f" ICMP Flood: src={src.name}({src.IP()}) -> {dst_ip}, ")  
    print("--------------------------------------------------------------------------------")
    print("Performing ICMP (Ping) Flood")  
    print("--------------------------------------------------------------------------------")   
    cmd = f"timeout 20s hping3 -1 -V -d  120 --flood {dst_ip}"
    src.cmd(cmd) 

    # Po zakończeniu całej symulacji, sprzątanie katalogów na wszystkich hostach
    for h in hosts:
        h.cmd(f"rm -rf {DOWNLOAD_DIR}")

    CLI(net)
    net.stop()

if __name__ == '__main__':   
    setLogLevel('info')

    start = datetime.now()

    start_network()

    end = datetime.now()

    print("Start time: ", start)
    print("End time: ", end)
    print("Duration: ", end - start)
