from mpg_explorer.scrap.goals import _count_icons_by_side


def test_count_icons_by_side_splits_by_midpoint():
    home_count, away_count = _count_icons_by_side(
        x_positions=[100.0, 220.0, 700.0, 820.0],
        viewport_width=1000.0,
    )

    assert home_count == 2
    assert away_count == 2


def test_count_icons_by_side_handles_empty_positions():
    home_count, away_count = _count_icons_by_side(
        x_positions=[],
        viewport_width=1000.0,
    )

    assert home_count == 0
    assert away_count == 0
