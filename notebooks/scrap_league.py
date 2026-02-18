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
from uuid import uuid4

import duckdb
import polars as pl

from mpg_explorer import LEAGUE_CONFIG, logger
from mpg_explorer.models.league_match_urls import LeagueMatchUrls
from mpg_explorer.models.match_result import Match
from mpg_explorer.scrap.game_info import get_match_data
from mpg_explorer.scrap.league import LeagueScrapper
from mpg_explorer.storage.league_matches_parquet import (
    save_scraped_league_matches_to_parquet,
)
from mpg_explorer.utils.driver import Driver


def scrape_league_matches_dataframe(
    league: LeagueScrapper, league_urls: LeagueMatchUrls | None = None
) -> pl.DataFrame:
    """
    Scrape all match data for a league and return a single dataframe.

    Args:
        league: Initialized LeagueScrapper.
        league_urls: Optional pre-scraped urls by matchweek. If None, they are scraped.

    Returns:
        pl.DataFrame: One row per match with league and matchweek metadata.
    """
    if league_urls is None:
        league_urls = league.find_matchs_urls_all_matchweeks()

    rows: list[dict] = []
    for matchweek_data in league_urls.matchweeks:
        matchweek = matchweek_data.matchweek
        logger.info(
            f"[matchweek={matchweek}] Scraping {len(matchweek_data.urls)} matches."
        )

        for match_url in matchweek_data.urls:
            league.driver.get(match_url)
            home_player, away_player = get_match_data(driver=league.driver)

            row = Match(
                match_id=str(uuid4()),
                league_id=league.league_id,
                division=league.division,
                season_number=league.season_nb,
                matchweek=matchweek,
                home_team_name=home_player.name,
                home_total_goals=home_player.score,
                home_bonus=home_player.list_bonus,
                visitor_team_name=away_player.name,
                visitor_total_goals=away_player.score,
                visitor_bonus=away_player.list_bonus,
            ).model_dump(mode="json")
            rows.append(row)

    return pl.DataFrame(rows)


# %%
logger.info("Scrapping data from MPG")
my_driver = Driver(docker=False)
my_driver.login_mpg(
    user=LEAGUE_CONFIG.MPG_USERNAME,
    password=LEAGUE_CONFIG.MPG_PASSWORD,
)

# %%
league = LeagueScrapper(driver=my_driver.driver, division=2)
league_urls = league.find_matchs_urls_all_matchweeks()
logger.info(f"Matchweeks scraped: {[m.matchweek for m in league_urls.matchweeks]}")

# %%
df_league = scrape_league_matches_dataframe(league=league, league_urls=league_urls)
logger.info(f"Found {df_league.shape[0]} matches.")
parquet_path = save_scraped_league_matches_to_parquet(
    df=df_league,
    league_id=league.league_id,
    season_number=league.season_nb,
    division=league.division,
)
logger.info(f"Saved parquet to: {parquet_path}")

# %%
df_duckdb = duckdb.sql(
    f"SELECT * FROM read_parquet('{parquet_path}') ORDER BY matchweek, home_team_name"
).pl()
df_duckdb

# %%
