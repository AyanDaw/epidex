# resolve_tool, check_dependencies, auto-install/auto-download logic

def resolve_tool(name: str, env_key: str) -> str:
    """Fixes the dependency checks. .env override first, PATH lookup second, exits with an actionable message otherwise."""
    configured = (config.get(env_key) or "").strip()
    if configured:
        if Path(configured).exists():
            return configured
        print(f"WARNING: {env_key} in .env points to '{configured}', but that path doesn't exist — falling back to PATH.")

    found = shutil.which(name)
    if found:
        return found

    if configured:
        sys.exit(f"ERROR: couldn't find '{name}' — the path in .env ('{configured}') doesn't exist, "
                  f"and it's not on PATH either. Fix {env_key} in .env or add {name} to PATH.")
    sys.exit(f"ERROR: '{name}' not found on PATH, and {env_key} isn't set in .env. "
              f"Install it, then either add it to PATH or set {env_key} in .env to its full path.")


def check_dependencies():
    global YT_DLP_BIN, DENO_BIN, MKVMERGE_BIN, MKVPROPEDIT_BIN
    YT_DLP_BIN = resolve_tool("yt-dlp", "YT_DLP_PATH")
    DENO_BIN = resolve_tool("deno", "DENO_PATH")
    MKVMERGE_BIN = resolve_tool("mkvmerge", "MKVMERGE_PATH")
    MKVPROPEDIT_BIN = resolve_tool("mkvpropedit", "MKVPROPEDIT_PATH")
    for label, path in [("yt-dlp", YT_DLP_BIN), ("deno", DENO_BIN),
                        ("mkvmerge", MKVMERGE_BIN), ("mkvpropedit", MKVPROPEDIT_BIN)]:
        try:
            subprocess.run([path, "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            sys.exit(f"ERROR: found a path for {label} ('{path}') but running it failed.")


def sync_resolved_paths_to_env():
    """After check_dependencies() resolves each tool - possibly via PATH, not .env -
    write the resolved paths back so next run skips the PATH lookup entirely."""
    data = dotenv_values(ENV_FILE)
    data["YT_DLP_PATH"] = YT_DLP_BIN or ""
    data["DENO_PATH"] = DENO_BIN or ""
    data["MKVMERGE_PATH"] = MKVMERGE_BIN or ""
    data["MKVPROPEDIT_PATH"] = MKVPROPEDIT_BIN or ""
    _write_env(data)