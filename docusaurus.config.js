// @ts-check
/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'OpenLabOps Wiki',
  tagline: 'Zero-Dependency Declarative Homelab Operations Framework',
  url: 'https://openlabops.github.io',
  baseUrl: '/openlabops/',
  organizationName: 'openlabops',
  projectName: 'openlabops',
  trailingSlash: false,

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'zh-TW', 'ja'],
    localeConfigs: {
      en: {
        label: 'English',
        htmlLang: 'en-US',
      },
      'zh-TW': {
        label: '繁體中文',
        htmlLang: 'zh-Hant-TW',
      },
      ja: {
        label: '日本語',
        htmlLang: 'ja-JP',
      },
    },
  },

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },
  themes: ['@docusaurus/theme-mermaid'],

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          routeBasePath: '/',
          sidebarPath: require.resolve('./sidebars.js'),
          editUrl: 'https://github.com/openlabops/openlabops/tree/wiki/',
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      navbar: {
        title: 'OpenLabOps Wiki',
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'wikiSidebar',
            position: 'left',
            label: 'Documentation',
          },
          {
            type: 'localeDropdown',
            position: 'right',
          },
          {
            href: 'https://github.com/openlabops/openlabops',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Wiki',
            items: [
              { label: 'Overview', to: '/' },
              { label: 'Architecture', to: '/architecture' },
              { label: 'Security Policy', to: '/security' },
              { label: 'Testing & Sandbox', to: '/testing' },
            ],
          },
          {
            title: 'CLI Reference',
            items: [
              { label: 'Onboarding & Provisioning', to: '/apps/onboarding-and-compiler' },
              { label: 'Fleet & SSH Lifecycle', to: '/apps/fleet-and-ssh' },
              { label: 'Config, Backup & Helpers', to: '/apps/ops-and-helpers' },
            ],
          },
          {
            title: 'Community',
            items: [
              {
                label: 'GitHub Repository',
                href: 'https://github.com/openlabops/openlabops',
              },
              {
                label: 'Releases (v1.0.0)',
                href: 'https://github.com/openlabops/openlabops/releases',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} OpenLabOps Maintainers. Licensed under Apache-2.0.`,
      },
    }),
};

module.exports = config;
