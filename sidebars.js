/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  wikiSidebar: [
    'intro',
    'architecture',
    'security',
    'testing',
    'methodology',
    {
      type: 'category',
      label: 'CLI Applications & Internals',
      items: [
        'apps/onboarding-and-compiler',
        'apps/fleet-and-ssh',
        'apps/ops-and-helpers',
      ],
    },
  ],
};

module.exports = sidebars;
