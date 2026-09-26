# Sourced by scripts: load .env.example then .env, but never override a variable that is
# already set in the environment (tests and callers pass their own ports and paths).
load_env_file() {
  local file=$1 line key
  [ -f "$file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    [[ $line =~ ^[[:space:]]*# ]] && continue
    [[ $line =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    key=${BASH_REMATCH[1]}
    [ -n "${!key+x}" ] && continue
    export "$key=${BASH_REMATCH[2]}"
  done <"$file"
}
# .env first so its values win over the defaults in .env.example.
load_env_file .env
load_env_file .env.example
