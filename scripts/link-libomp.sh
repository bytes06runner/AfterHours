#!/usr/bin/env bash
# LightGBM's macOS wheel links @rpath/libomp.dylib and looks for it only under Homebrew or
# MacPorts. Without Homebrew (installing it needs sudo), point LightGBM at the LLVM OpenMP
# runtime that scikit-learn's wheel already bundles. Changes stay inside .venv; rerun after
# reinstalling lightgbm. No-op on other platforms or when libomp is already found.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
[ "$(uname)" = "Darwin" ] || exit 0
export PATH="$HOME/.local/bin:$PATH"
if uv run --quiet python -c "import lightgbm" 2>/dev/null; then
  echo "link-libomp: lightgbm already loads"; exit 0
fi
site=$(uv run --quiet python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
lib="$site/lightgbm/lib/lib_lightgbm.dylib"
omp_dir="$site/sklearn/.dylibs"
[ -f "$omp_dir/libomp.dylib" ] || { echo "link-libomp: scikit-learn's libomp not found" >&2; exit 1; }
install_name_tool -add_rpath "$omp_dir" "$lib" 2>/dev/null || true
codesign --force --sign - "$lib"
uv run --quiet python -c "import lightgbm; print('link-libomp: lightgbm', lightgbm.__version__, 'loads')"
