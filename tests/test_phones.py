from information_hunters.phones import is_mobile, normalise_uk_phone, split_phone


def test_normalises_uk_mobile_and_trunk_prefix():
    assert normalise_uk_phone("+44 (0) 7700 900123") == "07700900123"
    assert normalise_uk_phone("+447700900123") == "07700900123"
    assert is_mobile("07700900123") is True


def test_landline_is_not_a_mobile():
    landline, mobile = split_phone("0161 496 0123")
    assert landline == "0161 496 0123"
    assert mobile is None


def test_personal_070_numbers_are_not_treated_as_mobiles():
    assert is_mobile(normalise_uk_phone("070 0090 0123")) is False
