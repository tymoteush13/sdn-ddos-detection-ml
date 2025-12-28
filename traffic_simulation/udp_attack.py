from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSKernelSwitch, RemoteController
import time
import random
from datetime import datetime

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

    NUM_ROUNDS = 10
    
    start_attacks = datetime.now()

    for round_num in range(1, NUM_ROUNDS + 1):
        
        # losowe parametry
        src = random.choice(hosts)
        dst = random.choice([h for h in hosts if h != src])
        dst_ip = dst.IP()
        packet_size = random.choice([64, 120, 512, 1024])
        duration = random.choice([10, 15, 20])

        print(f"[{round_num}] UDP Flood: src={src.name}({src.IP()}) -> {dst_ip}, "
          f"size={packet_size}B, duration={duration}s")

        # uruchomienie ataku UDP
        cmd = f"timeout {duration}s hping3 -2 -V -d {packet_size} --flood {dst_ip}"
        src.cmd(cmd)

        # przerwa
        sleep_time = 120
        time.sleep(sleep_time)

    end_attacks = datetime.now()

    print(f"Czas trwania ataku: {end_attacks - start_attacks}")

    CLI(net)
    net.stop()

if __name__ == '__main__':   
    setLogLevel('info')

    start_network()