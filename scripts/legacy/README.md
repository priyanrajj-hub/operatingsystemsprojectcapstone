# Legacy Scripts Archive

This directory archives historical one-off scripts and debug helpers used during early prototyping and preliminary benchmark log parsing.

## Summary of Archived Scripts

| Script | Original Purpose | Current Replacement |
|---|---|---|
| `compute_final.py` | Regex parser for `eval2.log` producing markdown tables & paired t-tests | Merged into `aidax.analysis` (`aidax-analysis` CLI) |
| `compute_safe.py` | Duplicate of `compute_final.py` handling UTF-16 log files | Merged into `aidax.analysis` |
| `dashboard.py` | Early Streamlit prototype dashboard | Replaced by production FastAPI WebSocket dashboard (`aidax.api` / `aidax-dashboard`) |
| `extract_url.py` | Regex scraper extracting Vercel deployment URLs from CLI text | Not needed in standard open-source workflow |
| `format_clean.py` | Pandas script aggregating last 20 rows of `results.csv` | Replaced by `aidax.analysis` |
| `format_results.py` | Duplicate of `format_clean.py` exporting markdown to `clean_output.txt` | Replaced by `aidax.analysis` (`--format markdown`) |
| `parse_log.py` | Log parser converting `eval2.log` to terminal markdown table | Replaced by `aidax.analysis` |
| `parse_log2.py` | Log parser converting `eval2.log` to JSON dictionary | Replaced by `aidax.analysis` (`--format json`) |

All analytical capabilities from these scripts (statistical aggregation, paired t-tests, markdown table generation, and JSON output) are now unified in `aidax.analysis`.
