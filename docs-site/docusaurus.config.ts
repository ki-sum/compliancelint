import { themes as prismThemes } from "prism-react-renderer";
import type { Config } from "@docusaurus/types";
import type * as Preset from "@docusaurus/preset-classic";

// This runs in Node.js — no browser APIs / JSX here.

const config: Config = {
  title: "ComplianceLint",
  tagline: "EU AI Act compliance scanner — auditable proof, not advice",
  favicon: "img/favicon.ico",

  future: {
    v4: true,
  },

  url: "https://docs.compliancelint.dev",
  baseUrl: "/",

  organizationName: "ki-sum",
  projectName: "compliancelint",

  // Don't fail the build on broken links/images during the first
  // iteration. Many cross-chapter `#section` anchors are aspirational
  // while the sidebar shape settles, and walkthrough PNGs may be
  // missing if the MDX references a chapter that hasn't had its
  // walkthrough re-run yet. Tighten to "throw" once content is final.
  onBrokenLinks: "warn",
  onBrokenMarkdownLinks: "warn",
  markdown: {
    hooks: {
      onBrokenMarkdownImages: "warn",
    },
  },

  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  presets: [
    [
      "classic",
      {
        docs: {
          sidebarPath: "./sidebars.ts",
          // No "Edit this page" link — MDX is generated, not directly
          // edited. Reviewers raise issues / send PRs against the
          // public repo and the team propagates upstream.
          editUrl: undefined,
          showLastUpdateTime: true,
        },
        // No blog for v1 — pure docs site. Re-enable later if we ship a
        // changelog or release notes blog.
        blog: false,
        theme: {
          customCss: "./src/css/custom.css",
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: "img/social-card.png",
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: "ComplianceLint",
      logo: {
        alt: "ComplianceLint logo",
        src: "img/logo.svg",
      },
      items: [
        {
          type: "docSidebar",
          sidebarId: "manualSidebar",
          position: "left",
          label: "User Manual",
        },
        {
          href: "https://compliancelint.dev",
          label: "Dashboard",
          position: "right",
        },
        {
          href: "https://github.com/ki-sum/compliancelint",
          label: "GitHub",
          position: "right",
        },
      ],
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Manual",
          items: [
            { label: "Quick Start", to: "/docs/quick-start" },
            { label: "Concept Primer", to: "/docs/concept-primer" },
            { label: "MCP Commands", to: "/docs/mcp-commands-reference" },
            { label: "Troubleshooting", to: "/docs/troubleshooting" },
          ],
        },
        {
          title: "Personas",
          items: [
            { label: "Provider", to: "/docs/persona-provider" },
            { label: "Deployer", to: "/docs/persona-deployer" },
            { label: "Authorised Rep", to: "/docs/persona-authorised-representative" },
            { label: "Importer", to: "/docs/persona-importer" },
            { label: "Distributor", to: "/docs/persona-distributor" },
          ],
        },
        {
          title: "Product",
          items: [
            { label: "Dashboard", href: "https://compliancelint.dev" },
            { label: "GitHub", href: "https://github.com/ki-sum/compliancelint" },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} ki-sum. ComplianceLint is open-source under BSL 1.1.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
