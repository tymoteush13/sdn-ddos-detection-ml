from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSKernelSwitch, RemoteController


class MyTopo (Topo):
    def build(self):

        # Tworzenie 6 switchy z protokoem Openflow (do komunikacji z kontrolerem)
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s3 = self.addSwitch('s3', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s4 = self.addSwitch('s4', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s5 = self.addSwitch('s5', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s6 = self.addSwitch('s6', cls=OVSKernelSwitch, protocols='OpenFlow13')

        # Tworzenie 20 hostow z mac-iem oraz ip
        hosts = []
        for i in range(1, 21):
            h = self.addHost(
                f'h{i}',
                mac=f'00:00:00:00:00:{i:02d}',
                ip=f'10.0.0.{i}/24'
            )
            hosts.append(h)

        # Dodawanie linkow
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
    # Budowa logiczna sieci
    topo = MyTopo()

    # Tworzenie zdalnego kontrolera (nazwa, ip oraz standardowy port OpenFlow)
    c0 = RemoteController('c0', ip='127.0.0.1', port=6653)

    # Tworzenie wirtualnej sieci z wlasna topologia, zdalnym kontrolerem oraz typem lacza (wbudowanego w Linuksie)
    net = Mininet(topo=topo, controller=c0, link=TCLink)

    net.start()

    # Interaktywna konsola Minineta
    CLI(net)

    net.stop()

if __name__ == '__main__':
    # Poziom logowania Minineta - 3 poziomy  
    setLogLevel('info')
    start_network()