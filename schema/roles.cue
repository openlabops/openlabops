package schema

// OpenLabOps Ansible Roles & Orchestration Contract Specification
// Models the 6 pure stateless generic Linux server roles.

#RoleName: "baseline" | "users" | "dotfiles" | "tools" | "docker_runtime" | "ssh_keys"

#AnsibleRole: {
	name:        #RoleName
	description: string
	supported_targets: [...("dev" | "servers" | "desktops")]
	allowed_tags: [...string]
}

#AnsibleRolesContract: {
	baseline: #AnsibleRole & {
		name:        "baseline"
		description: "Cross-distro Python bootstrap, timezone, base packages, sshd hardening, 2FA"
		supported_targets: ["dev", "servers", "desktops"]
		allowed_tags: ["baseline", "python_bootstrap", "sshd_harden"]
	}

	users: #AnsibleRole & {
		name:        "users"
		description: "Declarative user accounts, visudo validation, passwordless sudoers"
		supported_targets: ["dev", "servers", "desktops"]
		allowed_tags: ["users", "sudoers", "accounts"]
	}

	dotfiles: #AnsibleRole & {
		name:        "dotfiles"
		description: "Cross-platform shells (zsh/bash), Neovim/NvChad, SSH Client configs"
		supported_targets: ["dev", "servers", "desktops"]
		allowed_tags: ["dotfiles", "zsh", "nvim", "ssh_config"]
	}

	tools: #AnsibleRole & {
		name:        "tools"
		description: "Standard CLI toolchain distribution, /usr/local/bin symlinks"
		supported_targets: ["dev", "servers", "desktops"]
		allowed_tags: ["tools", "lab_cli", "symlinks"]
	}

	docker_runtime: #AnsibleRole & {
		name:        "docker_runtime"
		description: "Docker Compose runtime, Git post-push trigger hook, rolling reload"
		supported_targets: ["servers", "dev"]
		allowed_tags: ["docker", "compose", "post_push"]
	}

	ssh_keys: #AnsibleRole & {
		name:        "ssh_keys"
		description: "Three-phase zero-downtime key rotation"
		supported_targets: ["dev", "servers", "desktops"]
		allowed_tags: ["add_new_key", "verify_new_key", "remove_old_key", "rotate_keys", "update_commit_stamp"]
	}
}

roles_contract: #AnsibleRolesContract

// Anti-Pattern Defensive Rules:
#MonolithicPlaybookForbidden: true

