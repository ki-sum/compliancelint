import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

/**
 * ComplianceLint user manual sidebar.
 *
 * Grouped by reader intent (not by source persona dir) so a first-time
 * reader can skim the structure top-to-bottom and find the chapter that
 * matches their current question. The 5 persona addenda are collected
 * in their own group at the end since most readers only need their own
 * persona's chapter.
 *
 * Order is editorial — alphabetical doesn't make sense here (e.g.
 * Quick Start always first; Troubleshooting always last in workflow).
 */

const sidebars: SidebarsConfig = {
  manualSidebar: [
    {
      type: "category",
      label: "Get Started",
      collapsed: false,
      items: ["quick-start", "concept-primer", "getting-started"],
    },
    {
      type: "category",
      label: "Common Workflows",
      collapsed: false,
      items: [
        "dashboard-tour",
        "first-evidence-upload",
        "team-collaboration",
      ],
    },
    {
      type: "category",
      label: "Reference — Setup",
      collapsed: true,
      items: [
        "compliance-profile-setup",
        "profiling-wizard-deep-dive",
        "repo-settings",
        "settings-account",
        "plans-billing",
      ],
    },
    {
      type: "category",
      label: "Reference — Daily Use",
      collapsed: true,
      items: [
        "scans-page",
        "scan-detail-page",
        "findings-issues-page",
        "tasks-page",
        "human-gates-deep-dive",
      ],
    },
    {
      type: "category",
      label: "Reference — Output & Integration",
      collapsed: true,
      items: [
        "compliance-time-capsule",
        "sarif-export",
        "ci-cd-quality-gate",
        "regulation-updates",
        "eu-ai-act-browser",
      ],
    },
    {
      type: "category",
      label: "Personas",
      collapsed: true,
      items: [
        "persona-provider",
        "persona-deployer",
        "persona-authorised-representative",
        "persona-importer",
        "persona-distributor",
      ],
    },
    {
      type: "category",
      label: "Reference — Misc",
      collapsed: true,
      items: [
        "mcp-commands-reference",
        "enterprise-features",
        "notifications-and-privacy",
      ],
    },
    "troubleshooting",
  ],
};

export default sidebars;
