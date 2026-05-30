from src.ui.theme import dark_mode_from_setting, stylesheet


def test_dark_mode_from_setting() -> None:
    assert dark_mode_from_setting("1") is True
    assert dark_mode_from_setting("0") is False
    assert dark_mode_from_setting("") is False
    assert dark_mode_from_setting("yes") is True


def test_stylesheet_variants_differ() -> None:
    assert "QWidget" in stylesheet(dark=False)
    assert stylesheet(dark=True) != stylesheet(dark=False)


def test_stylesheet_uses_muted_accent() -> None:
    sheet = stylesheet(dark=False)
    assert "#5b5bd6" in sheet
    assert "searchInput" in sheet
    assert "navBrandBlock" in sheet
    assert "show-decoration-selected: 0" in sheet
    assert "formLabel" in sheet
    assert "btnIconDanger" in sheet
