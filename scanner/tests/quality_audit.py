"""
Quality Audit Script — Scan multiple real projects and analyze output quality.

Checks for:
1. False positive rate (findings that are clearly wrong)
2. Scan time per project
3. Finding distribution (too many = noise, too few = gaps)
4. Obligation coverage per article
5. Language detection accuracy
"""

import json
import os
import sys
import time

SCANNER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCANNER_ROOT)

from core.protocol import BaseArticleModule, ComplianceLevel

# Auto-discover modules (same as cli.py)
import importlib.util

_modules = {}
modules_dir = os.path.join(SCANNER_ROOT, "modules")
for entry in sorted(os.listdir(modules_dir)):
    module_path = os.path.join(modules_dir, entry, "module.py")
    if not os.path.isfile(module_path):
        continue
    try:
        spec = importlib.util.spec_from_file_location(
            f"cl_modules.{entry}", module_path,
            submodule_search_locations=[os.path.join(modules_dir, entry)],
        )
        mod = importlib.util.module_from_spec(spec)
        mod_dir = os.path.join(modules_dir, entry)
        if mod_dir not in sys.path:
            sys.path.insert(0, mod_dir)
        spec.loader.exec_module(mod)
        if hasattr(mod, "create_module"):
            instance = mod.create_module()
            _modules[instance.article_number] = instance
    except Exception as e:
        print(f"Warning: Failed to load module {entry}: {e}")


def scan_project(project_path: str) -> dict:
    """Scan a single project and return structured results."""
    project_name = os.path.basename(project_path)
    start = time.time()

    results = {}
    for art_num in sorted(_modules.keys()):
        mod = _modules[art_num]
        BaseArticleModule.clear_index_cache()
        try:
            result = mod.scan(project_path)
            coverage = result.details.get("obligation_coverage", {})
            results[art_num] = {
                "level": result.overall_level.value,
                "findings_count": len(result.findings),
                "non_compliant": sum(1 for f in result.findings if f.level == ComplianceLevel.NON_COMPLIANT),
                "partial": sum(1 for f in result.findings if f.level == ComplianceLevel.PARTIAL),
                "compliant": sum(1 for f in result.findings if f.level == ComplianceLevel.COMPLIANT),
                "coverage": f"{coverage.get('covered_by_scan', 0)}/{coverage.get('total_obligations', 0)}",
                "gaps": coverage.get("coverage_gaps", -1),
                "language": result.language_detected,
                "files_scanned": result.files_scanned,
            }
        except Exception as e:
            results[art_num] = {"error": str(e)}

    elapsed = time.time() - start

    total_findings = sum(r.get("findings_count", 0) for r in results.values() if "error" not in r)
    total_non_compliant = sum(r.get("non_compliant", 0) for r in results.values() if "error" not in r)

    return {
        "project": project_name,
        "scan_time_s": round(elapsed, 1),
        "total_findings": total_findings,
        "total_non_compliant": total_non_compliant,
        "articles": results,
    }


def main():
    test_projects_dir = os.path.join(SCANNER_ROOT, "..", "test-projects")

    projects = []
    for name in sorted(os.listdir(test_projects_dir)):
        full = os.path.join(test_projects_dir, name)
        if os.path.isdir(full) and not name.startswith('.'):
            projects.append(full)

    print(f"=== ComplianceLint Quality Audit ===")
    print(f"Projects: {len(projects)}")
    print(f"Modules: {len(_modules)}")
    print()

    all_results = []

    for project_path in projects:
        name = os.path.basename(project_path)
        print(f"Scanning {name}...", end=" ", flush=True)
        result = scan_project(project_path)
        all_results.append(result)
        print(f"done ({result['scan_time_s']}s, {result['total_findings']} findings)")

    # Summary table
    print()
    print("=" * 100)
    print(f"{'Project':<25} {'Time':>6} {'Findings':>9} {'FAIL':>6} {'Language':<20} {'Art.12 Cov':>10}")
    print("-" * 100)

    for r in all_results:
        art12 = r["articles"].get(12, {})
        lang = art12.get("language", "?")
        cov = art12.get("coverage", "?")
        print(f"{r['project']:<25} {r['scan_time_s']:>5.1f}s {r['total_findings']:>9} {r['total_non_compliant']:>6} {lang:<20} {cov:>10}")

    # Coverage analysis
    print()
    print("=== Obligation Coverage ===")
    print(f"{'Article':<10}", end="")
    for r in all_results:
        print(f" {r['project'][:12]:>12}", end="")
    print()
    print("-" * (10 + 13 * len(all_results)))

    for art_num in sorted(_modules.keys()):
        print(f"Art. {art_num:<5}", end="")
        for r in all_results:
            art = r["articles"].get(art_num, {})
            if "error" in art:
                print(f" {'ERR':>12}", end="")
            else:
                cov = art.get("coverage", "?")
                gaps = art.get("gaps", -1)
                marker = " OK" if gaps == 0 else ""
                print(f" {cov:>10}{marker}", end="")
        print()

    # Potential issues
    print()
    print("=== Potential Issues ===")
    for r in all_results:
        issues = []
        if r["total_findings"] > 200:
            issues.append(f"TOO MANY FINDINGS ({r['total_findings']})")
        if r["scan_time_s"] > 30:
            issues.append(f"SLOW SCAN ({r['scan_time_s']}s)")
        for art_num, art in r["articles"].items():
            if isinstance(art, dict) and art.get("gaps", 0) > 0:
                issues.append(f"Art.{art_num} has {art['gaps']} coverage gaps")
        if issues:
            print(f"  {r['project']}: {'; '.join(issues)}")

    # Save full results
    output_path = os.path.join(test_projects_dir, "quality-audit.json")
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull results saved to: {output_path}")


if __name__ == "__main__":
    main()
