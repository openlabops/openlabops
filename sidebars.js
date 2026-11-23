/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  wikiSidebar: [
    'intro',
    'architecture',
    {
      type: 'category',
      label: 'Design Concepts & Mechanisms',
      items: [
        'concepts/three-tier-ssot',
        'concepts/day0-ephemeral-bootstrap',
        'concepts/three-phase-key-rotation',
        'concepts/boot-sync-and-lockout',
        'concepts/sensory-cmdb-decoupling',
        'concepts/zero-dep-runner-model',
      ],
    },
    'security',
    'testing',
    'methodology',
    {
      type: 'category',
      label: 'CLI Applications & Internals',
      items: [
        'apps/lab-init',
        'apps/lab-node',
        'apps/lab-discover',
        'apps/lab-compiler',
        'apps/lab-status-and-ssh',
        'apps/lab-fleet-ops',
        'apps/lab-dev-and-helpers',
      ],
    },
  ],
};

module.exports = sidebars;
