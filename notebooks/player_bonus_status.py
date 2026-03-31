# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mpg-explorer",
#     "polars",
#     "matplotlib",
# ]
#
# [tool.uv.sources]
# mpg-explorer = { path = "../", editable = true }
# ///

# %%
from mpg_explorer import LEAGUE_CONFIG, logger
from mpg_explorer.reports.opponent_report import (
    export_error_report_html,
    export_opponent_report_html,
    load_matches_from_parquet,
)
from mpg_explorer.storage.utils import (
    get_scraped_league_matches_parquet_path,
)

# %%
parquet_path = get_scraped_league_matches_parquet_path(
    league_id=LEAGUE_CONFIG.LEAGUE_ID,
    season_number=LEAGUE_CONFIG.SEASON_NUMBER,
    division=LEAGUE_CONFIG.DIVISION,
    data_path=LEAGUE_CONFIG.DATA_PATH,
)
output_html_path = LEAGUE_CONFIG.DATA_PATH / "reports" / "next_opponent_report.html"

# %%
logger.info(f"Parquet file: {parquet_path}")
logger.info(f"My team: {LEAGUE_CONFIG.TEAM_NAME}")
try:
    df = load_matches_from_parquet(parquet_path)
    report_path, opponent_name = export_opponent_report_html(
        df=df,
        my_team_name=LEAGUE_CONFIG.TEAM_NAME,
        output_path=output_html_path,
    )
    logger.info(f"Next opponent: {opponent_name}")
except ValueError as exc:
    report_path = export_error_report_html(
        my_team_name=LEAGUE_CONFIG.TEAM_NAME,
        output_path=output_html_path,
        error_message=str(exc),
    )
    logger.error(f"Report generation fallback triggered: {exc}")

logger.info(f"HTML report exported to: {report_path}")


# %%
