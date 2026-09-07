from skills import preferences


def test_get_missing_preference_returns_none():
    result = preferences.get_preference(
        "default_shop",
        "default_payment_mode",
    )

    assert result is None


def test_set_and_get_preference():
    result = preferences.set_preference(
        "default_shop",
        "default_payment_mode",
        "upi",
    )

    assert result["owner_id"] == "default_shop"
    assert result["key"] == "default_payment_mode"
    assert result["value"] == "upi"

    assert (
        preferences.get_preference(
            "default_shop",
            "default_payment_mode",
        )
        == "upi"
    )


def test_set_preference_updates_existing_value():
    preferences.set_preference(
        "default_shop",
        "default_payment_mode",
        "upi",
    )

    preferences.set_preference(
        "default_shop",
        "default_payment_mode",
        "cash",
    )

    assert (
        preferences.get_preference(
            "default_shop",
            "default_payment_mode",
        )
        == "cash"
    )


def test_preferences_are_isolated_by_owner():
    preferences.set_preference(
        "shop_a",
        "default_payment_mode",
        "upi",
    )

    preferences.set_preference(
        "shop_b",
        "default_payment_mode",
        "cash",
    )

    assert (
        preferences.get_preference(
            "shop_a",
            "default_payment_mode",
        )
        == "upi"
    )

    assert (
        preferences.get_preference(
            "shop_b",
            "default_payment_mode",
        )
        == "cash"
    )