package schema

// OpenLabOps Network Topology Specification (Flat LAN)
// Single flat subnet for standard open-source homelab operations.

#Subnet: {
	name:        string
	cidr:        string
	description: string
	zone:        string
	allowed_inbound_from: [...string]
}

#CanonicalNetworkTables: {
	flat_lan: #Subnet & {
		name:        "flat_lan"
		cidr:        "192.168.1.0/24"
		description: "Standard Flat Local Area Network"
		zone:        "lan"
		allowed_inbound_from: ["flat_lan"]
	}
}

network_tables: #CanonicalNetworkTables

