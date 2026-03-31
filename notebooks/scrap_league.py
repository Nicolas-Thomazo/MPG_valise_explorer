# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mpg-explorer",
# ]
#
# [tool.uv.sources]
# mpg-explorer = { path = "../", editable = true }
# ///

# %%
import duckdb

from mpg_explorer import LEAGUE_CONFIG, logger
from mpg_explorer.reports.scrape_summary import export_scrape_summary_html
from mpg_explorer.scrap.league import LeagueScrapper
from mpg_explorer.utils.driver import Driver


# %%
logger.info("Scrapping data from MPG")
my_driver = Driver(docker=LEAGUE_CONFIG.IS_DOCKER)
my_driver.login_mpg(
    user=LEAGUE_CONFIG.MPG_USERNAME,
    password=LEAGUE_CONFIG.MPG_PASSWORD,
)

# %%
league = LeagueScrapper(driver=my_driver.driver, division=LEAGUE_CONFIG.DIVISION)
df_league, parquet_path = league.scrape_and_save_league(
    data_path=LEAGUE_CONFIG.DATA_PATH
)

# %%
logger.info(f"Found {df_league.shape[0]} matches.")
logger.info(f"Saved parquet to: {parquet_path}")
summary_report_path = export_scrape_summary_html(
    df=df_league,
    division=LEAGUE_CONFIG.DIVISION,
    season_number=LEAGUE_CONFIG.SEASON_NUMBER,
    output_path=LEAGUE_CONFIG.DATA_PATH / "reports" / "scrape_summary.html",
)
logger.info(f"Saved scrape summary report to: {summary_report_path}")

# %%
df_duckdb = duckdb.sql(
    f"SELECT * FROM read_parquet('{parquet_path}') ORDER BY matchweek, home_team_name"
).pl()
df_duckdb

# %%
