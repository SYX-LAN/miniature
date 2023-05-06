#!/usr/bin/python

import sys
import ipaddress
from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel, debug
from mininet.util import (ipAdd)

from mininet.node import (KindNode)
from subprocess import Popen, PIPE

class kubeSimCLI( CLI ):
	prompt = "miniature>"
	
	def __init__(self, mininet, stdin=sys.stdin, script=None):
		super().__init__(mininet, stdin, script)
		

class kubeCluster( Containernet ):
	def __init__(self, **params):
		Containernet.__init__(self, **params)
		self.clusters = {}
		self.linksNotProcessed = []
		self.usedIP = []

	def addKubeCluster(self,  name, minIP = '172.16.0.0', maxIP = '172.31.255.255', **params):
		if name in self.clusters:
			error("Cluster %s exists!" % name)
			exit(0)
		else:
			if (ipaddress.ip_address(minIP) < ipaddress.ip_address('172.16.0.0')) or (
				ipaddress.ip_address(maxIP) > ipaddress.ip_address('172.31.255.255')):
				error("Custom IP range is out of classB internal IP range")
				exit(0)
			self.kindClusters.append(name)
			cluster = KubeSim()
			self.clusters[name] = cluster
			cluster.addKubeCluster(name, minIP, maxIP, self.usedIP, **params)
			cluster.belonging = self
			cluster.useIP = self.usedIP
		return cluster

	def start(self):
		if len(self.clusters) > 0:
			# iterate over values
			for cluster in self.clusters.values():
				if len(cluster.kubeNodes) > 0:
					cluster.boostKubeCluster()
					for k in cluster.kubeNodes:
						cluster.kubeNodes[k].init()
		for l in self.linksNotProcessed:
			Containernet.addLink(self, l[0], l[1], port1=l[2], port2=l[3], cls=l[4], **l[5])
		Containernet.start(self)
		for cluster in self.clusters.values():
			for k in cluster.kubeNodes:
				cluster.kubeNodes[k].bringIntfUp()
				cluster.kubeNodes[k].setupKube()

	def addLink( self, node1, node2, port1=None, port2=None,
				 cls=None, **params ):
		# delays to add link
		self.linksNotProcessed.append((node1, node2, port1, port2, cls, params))



class KubeSim():
	def __init__(self, **params):
		# call original Containernet.__init__
		Containernet.__init__(self, **params)
		self.kubeNodes = {}
		self.linksNotProcessed = []
		self.clusterName = ""
		self.numController = 0
		self.numWorker = 0
		self.belonging = None
		self.minIP = ipaddress.ip_address('172.16.0.0')
		self.maxIP = ipaddress.ip_address('172.31.255.255')
		self.IPcounter = ipaddress.ip_address('172.16.0.0')
		self.usedIP = []

	def addKubeCluster(self, name, minIP, maxIP, usedIP, **params):
		if name == self.clusterName:
			error("Cluster %s exists!" % name)
		else:
			self.clusterName = name
			self.minIP = ipaddress.ip_address(minIP)
			self.maxIP = ipaddress.ip_address(maxIP)
			self.IPcounter = ipaddress.ip_address(minIP)
			self.usedIP = usedIP

		#support multiple cluster, now only 1 supported. finished
		#TODO: deal with the config file

	def addKubeNode(self, clusterName, name, **params):
		if params.get('type', "kind") != "kind":
			error("Only supporting Kind node now!")
		else:
			params["cls"] = KindNode

		role = params.get("role", "worker")
		cname = clusterName + "-"
		if role == "worker":
			cname = cname + "worker" + ("" if self.numWorker == 0 else str(self.numWorker))
			self.numWorker += 1
		elif role == "control-plane":
			cname = cname + "control-plane" + ("" if self.numController == 0 else str(self.numController))
			self.numController += 1
		else:
			error("Unknown role %s!" % role)

		defaults = {"cname": cname}
		defaults.update( params )

		# TODO: may need to have a sperate IP range than the default ones
		# This IP now is not being used. 
		# user-defined IP is not supported now.

		while(True):
			if self.IPcounter > self.maxIP:
				error("Custom IP range used UP when adding node!")
				exit(0)
			if not (self.IPcounter in self.usedIP):
				self.usedIP.append(self.IPcounter)
				self.IPcounter += 1
				break
			else:
				self.IPcounter += 1
		nodeIP = str(self.IPcounter)
		self.kubeNodes[name] = self._addKubeNode(name, nodeIP, **defaults)
		return self.kubeNodes[name]

	def start(self):
		# deal with kind
		# Now by default it's kind node, can integrate other kind of node. 
		if len(self.kubeNodes) > 0:
		   self.boostKubeCluster()

		for k in self.kubeNodes:
			self.kubeNodes[k].init()
			# TODO:allowing to add sth other than kind?
			# TODO: make sure the container ID and process ID is get

		for l in self.linksNotProcessed:
			Containernet.addLink(self, l[0], l[1], port1=l[2], port2=l[3], cls=l[4], **l[5])

		Containernet.start(self)

		for k in self.kubeNodes:
			self.kubeNodes[k].bringIntfUp()
			self.kubeNodes[k].setupKube()

	def addLink( self, node1, node2, port1=None, port2=None,
				 cls=None, **params ):
		# delays to add link 
		self.linksNotProcessed.append((node1, node2, port1, port2, cls, params))

	def _addKubeNode(self, name, nodeIP, cls=KindNode, **params):
		"""
		This starts a stub class of KubeNode, and not start a container
		"""
		return self.belonging.addHost(name, cls=cls, **params)

	def generateKindConfig(self, name, cluster):
		#enforce certain resource limits
		s = "kind: Cluster\napiVersion: kind.x-k8s.io/v1alpha4\nnodes: \n"
		extraMounts = "  extraMounts:\n  - hostPath: /usr/bin/ping\n    containerPath: " \
							+ "/usr/bin/ping\n"
		control_plane_mode = '  kubeadmConfigPatches:\n  - |\n    kind: InitConfiguration\n    nodeRegistration:\n      kubeletExtraArgs:'
		worker_mode = '  kubeadmConfigPatches:\n  - |\n    kind: JoinConfiguration\n    nodeRegistration:\n      kubeletExtraArgs:'

		for k in cluster:
			s = s + "- role: " + cluster[k].role + "\n"
			kube_args = None
			system_args = None

			if cluster[k].kube_reserved_cpu is not None:
				kube_args = "\n        kube-reserved: cpu=" + str(cluster[k].kube_reserved_cpu)
			if cluster[k].kube_reserved_memory is not None:
				if kube_args is None:
					kube_args = "\n        kube-reserved: memory=" + str(cluster[k].kube_reserved_memory)
				else:
					kube_args += ", memory=" + str(cluster[k].kube_reserved_memory)

			if cluster[k].system_reserved_cpu is not None:
				system_args = "\n        system-reserved: cpu=" + str(cluster[k].system_reserved_cpu)
			if cluster[k].system_reserved_memory is not None:
				if system_args is None:
					system_args = "\n        system-reserved: memory=" + str(cluster[k].system_reserved_memory)
				else:
					system_args += ", memory=" + str(cluster[k].system_reserved_memory)

			if kube_args is not None or system_args is not None:
				if cluster[k].role == 'worker':
					s += worker_mode
				else:
					s += control_plane_mode
				if kube_args is not None:
					s += kube_args
				if system_args is not None:
					s += system_args
				s += "\n"
			s += extraMounts

		configPath = "config/kubsim_cluster_" + name + ".yaml"

		with open(configPath, "w") as f:
			f.write(s)

		info("** Kind Config Created **\n")
		return configPath

	def boostKubeCluster(self):
		# Get cluster infomaiton
		info("** Bootstrapping Kind Cluster **\n")
		info("Number of workers %s\nNumber of control-plane %s\n" % (self.numWorker, self.numController))

		if self.numController == 0:
			error("No control plane for kubernetes cluster!")

		configPath = self.generateKindConfig(self.clusterName, self.kubeNodes)

		debug(self.pexec(["kind", "create", "cluster", "--name", self.clusterName, 
							"--config", configPath]))
		# TODO: need to parse the output of kind to make sure it's created
		info("**Cluster created successfully!**")

	def pexec( self, cmd ):
		"""Execute a command using popen
		   returns: out, err, exitcode"""
		popen = Popen( cmd, stdout=PIPE, stderr=PIPE)
		# Warning: this can fail with large numbers of fds!
		out, err = popen.communicate()
		exitcode = popen.wait()
		return cmd, out, err, exitcode

