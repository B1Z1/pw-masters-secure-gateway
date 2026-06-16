"""Pure checksum & derivation tests (T020, FR-008..FR-011, SC-009)."""

from __future__ import annotations

from gateway_api.detection.checksums import (
    nip_is_valid,
    nrb_is_valid,
    pesel_birth_date,
    pesel_gender,
    pesel_is_valid,
    regon9_is_valid,
    regon14_is_valid,
)


# --- PESEL ---
def test_pesel_valid():
    assert pesel_is_valid("44051401359") is True


def test_pesel_invalid_checksum():
    assert pesel_is_valid("44051401358") is False


def test_pesel_wrong_length():
    assert pesel_is_valid("4405140135") is False
    assert pesel_is_valid("440514013590") is False


def test_pesel_gender_even_is_female_odd_is_male():
    assert pesel_gender("44051401340") == "female"  # index 9 = '4'
    assert pesel_gender("44051401359") == "male"  # index 9 = '5'


def test_pesel_birth_date_1900s():
    assert pesel_birth_date("44051401359") == "1944-05-14"


def test_pesel_birth_date_post_2000_month_offset():
    # yy=02, mm=21 -> January 2000s, dd=10 (SC-009).
    assert pesel_birth_date("02211012345") == "2002-01-10"


def test_pesel_birth_date_incoherent_returns_none():
    assert pesel_birth_date("00993199999") is None  # month 99 invalid


# --- NIP ---
def test_nip_valid():
    assert nip_is_valid("1234563218") is True


def test_nip_leading_zero_is_valid():
    # "0123456789" — control digit 9 matches; leading zero accepted (FR-009).
    assert nip_is_valid("0123456789") is True


def test_nip_invalid_checksum():
    assert nip_is_valid("1234567890") is False


def test_nip_control_10_is_invalid():
    # first-9 weighted sum = 9*6 = 54, 54 % 11 = 10 -> must be rejected.
    assert nip_is_valid("9000000000") is False


# --- REGON ---
def test_regon9_valid():
    assert regon9_is_valid("123456785") is True


def test_regon9_invalid():
    assert regon9_is_valid("123456789") is False


def test_regon14_valid():
    assert regon14_is_valid("12345678500002") is True


def test_regon14_invalid():
    assert regon14_is_valid("12345678500009") is False


# --- Bank account (mod-97) ---
def test_nrb_valid():
    # Wikipedia PL IBAN example: PL61 1090 1014 0000 0712 1981 2874.
    assert nrb_is_valid("61109010140000071219812874") is True


def test_nrb_invalid():
    assert nrb_is_valid("61109010140000071219812875") is False


def test_nrb_wrong_length():
    assert nrb_is_valid("123") is False
