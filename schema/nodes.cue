package schema

// OpenLabOps Pure Linux Node Schema
// Enforces standard Linux classification on Flat LAN [INV-04, INV-12]

#NodeClass:     "standard"
#NodeCategory:  "standard" | "server" | "desktop" | "dev"
#KeyProfile:    "standard"
#ApplianceType: "none"

#OpenLabNode: close({
	hostname:       string
	fqdn?:          string
	primary_ip:     string & =~"^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}$"
	subnet_cidr?:   string & =~"^[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}/[0-9]{1,2}$"
	node_class?:    #NodeClass
	standard_role?: "dev" | "server" | "desktop"
	node_category:  #NodeCategory
	always_online:  bool
	is_immutable:   bool
	key_profile:    #KeyProfile
	appliance_type: #ApplianceType
	os_family:      string
	distribution:   string
	ssh_port?:      int & >=1 & <=65535

	capabilities: close({
		has_docker:  bool
		has_python:  bool
		is_gateway?: bool
	})
})

#NodeTelemetry: #OpenLabNode
#NodesSnapshot: [...#OpenLabNode]
