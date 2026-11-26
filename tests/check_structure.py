"""Assert-based structure checks, run through tests.self_check."""

from pathlib import Path
import sys


def check_project_structure():
    import importlib

    modules = (
        "bb84_lab.local.server", "bb84_lab.core.bb84", "bb84_lab.core.e91",
        "bb84_lab.simulation.session", "bb84_lab.core.postprocess",
        "bb84_lab.core.secure_channel", "bb84_lab.research.analysis", "bb84_lab.simulation.education",
        "bb84_lab.research.experiments", "bb84_lab.research.study",
        "bb84_lab.core.e91_key", "bb84_lab.simulation.comparison",
        "bb84_lab.research.comparison", "bb84_lab.research.comparison_analysis",
        "bb84_lab.research.plot_comparison", "bb84_lab.network.benchmark",
        "bb84_lab.research.plot_results", "bb84_lab.research.verify_quantum",
        "bb84_lab.network", "bb84_lab.network.config", "bb84_lab.network.transport",
        "bb84_lab.network.session", "bb84_lab.network.packets", "bb84_lab.network.transfer",
        "bb84_lab.network.service", "bb84_lab.network.proxy", "bb84_lab.network.ui",
        "bb84_lab.local.cli", "bb84_lab.simulation.cli", "bb84_lab.network.cli",
        "bb84_lab.shared.paths", "bb84_lab.shared.http",
    )
    root = Path(__file__).resolve().parents[1]
    assert not list(root.glob("*.py")), "Mã Python phải nằm trong package hoặc tests"
    assert {path.name for path in (root / "bb84_lab").glob("*.py")} == {"__init__.py"}
    for canonical in modules:
        module = importlib.import_module(canonical)
        relative = canonical.replace(".", "/")
        expected = root / relative / "__init__.py" if hasattr(module, "__path__") else root / (relative + ".py")
        assert Path(module.__file__).resolve() == expected
    from bb84_lab.local.server import make_server
    from bb84_lab.shared.paths import PROJECT_ROOT, WEB_ROOT, CONFIG_ROOT, OUTPUT_ROOT
    assert PROJECT_ROOT == root and WEB_ROOT == root / "web"
    assert CONFIG_ROOT == root / "configs" and OUTPUT_ROOT == root / "outputs"
    for relative in ("web/simulation/index.html", "web/simulation/app.js", "web/simulation/education.js",
                     "web/simulation/e91.js", "web/simulation/e91.css", "web/shared/styles.css",
                     "configs/smoke.json", "configs/main.json", "configs/study.json",
                     "web/network/index.html", "web/network/app.js", "web/network/styles.css",
                     "docs/NETWORK_DEMO.md", "docs/DEMO.md", "docs/de_cuong_QKD_3_tuan.md"):
        assert (root / relative).is_file(), relative
    assert make_server.__defaults__[1] == root / "outputs" / "study"
    assert not any(name.split(".")[0] in {"matplotlib", "qiskit", "qiskit_aer"}
                   for name in sys.modules)

    # Enforce domain boundaries so dashboard/network code cannot leak into core.
    import ast
    allowed = {
        "core": {"core"}, "simulation": {"core", "simulation"},
        "local": {"core", "simulation", "local", "shared"},
        "network": {"core", "network", "shared"},
        "research": {"core", "simulation", "research", "shared"},
        "shared": {"shared"},
    }
    for domain, dependencies in allowed.items():
        for file in (root / "bb84_lab" / domain).rglob("*.py"):
            for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
                imports = [node.module or ""] if isinstance(node, ast.ImportFrom) else (
                    [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                for module in imports:
                    if module.startswith("bb84_lab."):
                        assert module.split(".")[1] in dependencies, (file, module)
