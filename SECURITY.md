# Security & Maintenance Policy

## 🔒 Architectural Security Model

OpenLabOps is designed from the ground up for private infrastructure, local homelabs, and air-gapped environments. Its security model is strictly enforced by code and tests:

1. **[INV-01] Zero Supply-Chain Risk (Zero External Python Dependencies)**:
   - Built with **100% Python standard library**.
   - No `pip install`, no third-party package dependencies (`requests`, `pyyaml`, `paramiko`, etc.), completely eliminating external dependency supply-chain attack vectors.

2. **[INV-02] Zero Private Keys in Repository**:
   - Private SSH keys (`*.key`, `id_*`) are **STRICTLY FORBIDDEN** in the Git repository.
   - All management private keys reside exclusively on the designated administrator workstation in `~/.ssh/`.

3. **Three-Phase Zero-Downtime Key Rotation**:
   - Key replacement follows a strict atomic lifecycle: **Add new key $\rightarrow$ Verify connectivity $\rightarrow$ Revoke retired key**.
   - Remote key revocation only strips project-managed automation public keys, preserving user custom keys and interactive login credentials.

4. **Network Scoping & Lockout Guards**:
   - Management keys in `authorized_keys` are constrained by `from="<subnet>"` where configured.
   - Local validation checks protect against configuration lockout before applying changes.

---

## ⚖️ Maintenance & Disclaimer Notice

* **"AS IS" License**: This software is released under the **Apache License 2.0**. It is provided on an "AS IS" basis, without warranties or conditions of any kind, either express or implied.
* **No Maintenance SLA / No Commercial Obligations**: This is an independent, community-shared homelab automation framework. The maintainers do not offer commercial support, on-call guarantees, or SLAs for patch turnarounds.
* **Issues & Pull Requests Policy**:
  - GitHub Issues and Pull Requests are **disabled/closed**.
  - Maintenance is upstream-directed; feature requests and unsolicited PRs will not be triaged.
* **Discussions & Forking**:
  - If you find a bug, have an architecture idea, or want to discuss usage, feel free to use **GitHub Discussions**.
  - If you need custom behavior, bug fixes, or specific distribution adaptations for your environment, **you are warmly encouraged to fork this repository** and customize it to your heart's content.
