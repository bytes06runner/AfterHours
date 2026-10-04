"""Keep the hosted API small (Render free has 512 MB): heavy modules stay off its import path."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from afterhours.config import load_config

REPO = Path(__file__).resolve().parents[2]


def test_api_import_loads_no_scipy_or_yfinance() -> None:
    code = (
        "import sys, afterhours.api.app as a; a.create_app(); "
        "print(sorted({m.split('.')[0] for m in sys.modules} & "
        "{'scipy', 'yfinance', 'curl_cffi', 'lightgbm', 'sklearn', 'matplotlib', 'lxml'}))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def test_normal_quantile_matches_scipy() -> None:
    from scipy.stats import norm

    from afterhours.risk.live import NORMAL

    alpha = float(load_config(load_env_file=False).model.target_alpha)
    assert NORMAL.inv_cdf(alpha) == float(norm.ppf(alpha))  # bit for bit at the shipped alpha


def test_serve_prefetches_prices_outside_the_api() -> None:
    serve = (REPO / "scripts" / "serve.sh").read_text()
    fetch = serve.index("data fetch --stock-tokens")
    assert fetch < serve.index('exec "${AH[@]}" api')
    assert "AFTERHOURS_LIVE__WARM_PRICES=false" in serve
