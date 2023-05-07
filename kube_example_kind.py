#!/usr/bin/python
"""
This is the most simple example to showcase Containernet.
"""
from mininet.net import Containernet
from mininet.node import Controller
# from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from kubesim import KubeSim
from kubesim import kubeCluster
from kubesim import kubeSimCLI
# def tracefunc(frame, event, arg, indent=[0]):
#      if event == "call":
#          indent[0] += 2
#          print("-" * indent[0] + "> call function", frame.f_code.co_name)
#      elif event == "return":
#          print("<" + "-" * indent[0], "exit function", frame.f_code.co_name)
#          indent[0] -= 2
#      return tracefunc

# import sys
# sys.setprofile(tracefunc)

setLogLevel('info')

net = kubeCluster(controller=Controller)
info('*** Adding controller\n')
net.addController('c10')
info('*** Adding docker containers\n')
c1 = net.addKubeCluster("test", config="config/kind.yaml")
info('*** Adding docker container 1\n')
k1 = c1.addKubeNode("test", "k1", role="control-plane", type="kind")
info('*** Adding docker container 2\n')
k2 = c1.addKubeNode("test", "k2", role="worker", type="kind", drop_rate=0.5)
info('*** finished\n')
d1 = net.addDocker('d1', ip='172.18.0.10', dimage="ubuntu:trusty")
# net.addKubeClusterConfig()
info('*** Second Cluster\n')
# c2 = net.addKubeCluster("t", config = "config/kind.yaml")
# k3 = c2.addKubeNode("t", "k3", role = "control-plane", type = "kind")
# k4 = c2.addKubeNode("t", "k4", role = "worker", type = "kind")
info('*** Adding switches\n')
s1 = net.addSwitch('s1')
s2 = net.addSwitch('s2')
# s2 = net.addSwitch('s2')
info('*** Creating links\n')
net.addLink(k1, s1)
# net.addLink(k3, s1)
# net.addLink(k4, s1)
# net.addLink(s1, s2, cls=TCLink, delay='100ms', bw=1)
net.addLink(s1, k2)
net.addLink(s1, d1)
info('*** Starting network\n')
net.start()
info('*** Testing connectivity\n')
# net.ping([k1, k2])
# net.ping([k1, d1])
# net.ping([k3, k4])
# net.ping([k1, k3])
info('*** Running CLI\n')
kubeSimCLI(net)
info('*** Stopping network')
net.stop()
