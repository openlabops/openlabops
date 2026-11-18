package schema

// OpenLabOps Canonical Key Roles & Security Contract Specification
// Models the 3 fundamental key roles in the architecture: ansible, user, git.

#CanonicalKeyRole: "ansible" | "user" | "git"

#KeyDefinition: {
	role:                      #CanonicalKeyRole
	description:               string
	algorithm:                 "ed25519" | "rsa"
	target_user:               string
	requires_from_restriction: bool
}

#CanonicalKeysContract: {
	ansible: #KeyDefinition & {
		role:                      "ansible"
		description:               "Automated Ansible management and CI/CD operations"
		algorithm:                 "ed25519"
		target_user:               "ansible_user"
		requires_from_restriction: true
	}
	user: #KeyDefinition & {
		role:                      "user"
		description:               "Human operator login, admin actions, and workstation endpoints"
		algorithm:                 "ed25519"
		target_user:               "admin_user"
		requires_from_restriction: false
	}
	git: #KeyDefinition & {
		role:                      "git"
		description:               "Version control platform SSH access (Gitea/GitHub)"
		algorithm:                 "ed25519"
		target_user:               "git"
		requires_from_restriction: false
	}
}

#SiteKeyMapping: {
	ansible: string & =~"\\.key$"
	user:    string & =~"\\.key$"
	git:     string & =~"\\.key$"
}
