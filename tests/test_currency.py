# ABOUTME: Unit tests for the Currency system
# ABOUTME: Tests conversion rates, change-making, consolidation, and operations

import pytest
from dnd_engine.systems.currency import Currency


class TestCurrencyCreation:
    """Test Currency object creation and initialization"""

    def test_create_empty_currency(self):
        """Test creating an empty currency object"""
        currency = Currency()
        assert currency.copper == 0
        assert currency.silver == 0
        assert currency.electrum == 0
        assert currency.gold == 0
        assert currency.platinum == 0

    def test_create_currency_with_values(self):
        """Test creating currency with initial values"""
        currency = Currency(copper=5, silver=3, gold=10)
        assert currency.copper == 5
        assert currency.silver == 3
        assert currency.electrum == 0
        assert currency.gold == 10
        assert currency.platinum == 0

    def test_create_currency_with_negative_values_raises_error(self):
        """Test that negative values raise ValueError"""
        with pytest.raises(ValueError):
            Currency(gold=-5)

        with pytest.raises(ValueError):
            Currency(silver=-1)

    def test_is_zero(self):
        """Test is_zero method"""
        empty = Currency()
        assert empty.is_zero()

        with_value = Currency(gold=5)
        assert not with_value.is_zero()

        copper_only = Currency(copper=1)
        assert not copper_only.is_zero()


class TestCurrencyConversion:
    """Test conversion rates and to_copper method"""

    def test_conversion_rates_are_correct(self):
        """Verify D&D 5E conversion rates"""
        assert Currency.CP_PER_SP == 10
        assert Currency.CP_PER_EP == 50
        assert Currency.CP_PER_GP == 100
        assert Currency.CP_PER_PP == 1000

    def test_to_copper_empty(self):
        """Test converting empty currency to copper"""
        currency = Currency()
        assert currency.to_copper() == 0

    def test_to_copper_single_denomination(self):
        """Test converting single denomination to copper"""
        assert Currency(copper=5).to_copper() == 5
        assert Currency(silver=1).to_copper() == 10
        assert Currency(electrum=1).to_copper() == 50
        assert Currency(gold=1).to_copper() == 100
        assert Currency(platinum=1).to_copper() == 1000

    def test_to_copper_multiple_denominations(self):
        """Test converting multiple denominations to copper"""
        # 1 gp (100 cp) + 1 sp (10 cp) + 5 cp = 115 cp
        currency = Currency(copper=5, silver=1, gold=1)
        assert currency.to_copper() == 115

        # 1 pp (1000 cp) + 2 gp (200 cp) + 3 ep (150 cp) = 1350 cp
        currency = Currency(electrum=3, gold=2, platinum=1)
        assert currency.to_copper() == 1350

    def test_to_copper_large_amounts(self):
        """Test converting large amounts"""
        currency = Currency(platinum=10, gold=50, silver=100)
        # 10 * 1000 + 50 * 100 + 100 * 10 = 10000 + 5000 + 1000 = 16000
        assert currency.to_copper() == 16000


class TestCurrencyAddition:
    """Test adding currencies together"""

    def test_add_empty_to_empty(self):
        """Test adding empty currencies"""
        c1 = Currency()
        c2 = Currency()
        c1.add(c2)
        assert c1.is_zero()

    def test_add_to_empty(self):
        """Test adding currency to empty inventory"""
        c1 = Currency()
        c2 = Currency(gold=5, silver=3)
        c1.add(c2)
        assert c1.gold == 5
        assert c1.silver == 3

    def test_add_same_denomination(self):
        """Test adding same denominations"""
        c1 = Currency(gold=5)
        c2 = Currency(gold=3)
        c1.add(c2)
        assert c1.gold == 8
        assert c1.silver == 0

    def test_add_different_denominations(self):
        """Test adding different denominations"""
        c1 = Currency(gold=5, copper=10)
        c2 = Currency(platinum=1, silver=3)
        c1.add(c2)
        assert c1.platinum == 1
        assert c1.gold == 5
        assert c1.silver == 3
        assert c1.copper == 10

    def test_add_non_currency_raises_error(self):
        """Test that adding non-Currency object raises error"""
        c1 = Currency()
        with pytest.raises(ValueError):
            c1.add(5)

        with pytest.raises(ValueError):
            c1.add("gold")


class TestCurrencySubtraction:
    """Test subtracting currencies with change-making"""

    def test_subtract_exact_amount(self):
        """Test subtracting exact amount available"""
        c1 = Currency(gold=5, silver=3)
        c2 = Currency(gold=2, silver=1)
        result = c1.subtract(c2)
        assert result is True
        assert c1.gold == 3
        assert c1.silver == 2

    def test_subtract_insufficient_funds(self):
        """Test subtracting more than available"""
        c1 = Currency(gold=2)
        c2 = Currency(gold=5)
        result = c1.subtract(c2)
        assert result is False
        assert c1.gold == 2  # Unchanged

    def test_subtract_zero(self):
        """Test subtracting zero currency"""
        c1 = Currency(gold=5)
        c2 = Currency()
        result = c1.subtract(c2)
        assert result is True
        assert c1.gold == 5

    def test_subtract_with_exact_change_making(self):
        """Test paying with exact change after making change"""
        # Have 1 gp (100 cp), pay 50 cp, left with 50 cp (consolidated form = 1 ep)
        c1 = Currency(gold=1)
        c2 = Currency(copper=50)
        result = c1.subtract(c2)
        assert result is True
        assert c1.to_copper() == 50
        assert c1.electrum == 1  # 50 cp = 1 ep (consolidated form)

    def test_subtract_non_currency_raises_error(self):
        """Test that subtracting non-Currency object raises error"""
        c1 = Currency()
        with pytest.raises(ValueError):
            c1.subtract(5)


class TestCurrencyAffordability:
    """Test checking if currency can afford amounts"""

    def test_can_afford_same_amount(self):
        """Test checking affordability for same amount"""
        c1 = Currency(gold=5)
        c2 = Currency(gold=5)
        assert c1.can_afford(c2) is True

    def test_can_afford_less_amount(self):
        """Test checking affordability for less amount"""
        c1 = Currency(gold=5)
        c2 = Currency(gold=3)
        assert c1.can_afford(c2) is True

    def test_cannot_afford(self):
        """Test checking affordability when insufficient"""
        c1 = Currency(gold=2)
        c2 = Currency(gold=5)
        assert c1.can_afford(c2) is False

    def test_can_afford_with_mixed_denominations(self):
        """Test affordability with mixed denominations"""
        # Have 1 gp + 5 sp = 150 cp
        c1 = Currency(gold=1, silver=5)
        # Need 100 cp (1 gp)
        c2 = Currency(gold=1)
        assert c1.can_afford(c2) is True

        # Need 60 cp
        c3 = Currency(silver=6)
        assert c1.can_afford(c3) is True

    def test_can_afford_non_currency_raises_error(self):
        """Test that checking non-Currency raises error"""
        c1 = Currency()
        with pytest.raises(ValueError):
            c1.can_afford(5)


class TestCurrencyConsolidation:
    """Test consolidating currency to larger denominations"""

    def test_consolidate_copper_to_silver(self):
        """Test converting 10+ copper to silver"""
        currency = Currency(copper=25)
        currency.consolidate()
        assert currency.silver == 2
        assert currency.copper == 5

    def test_consolidate_silver_to_electrum(self):
        """Test converting silver to electrum and above"""
        currency = Currency(silver=12)
        currency.consolidate()
        # 12 sp = 120 cp = 1 gp + 2 sp (cascading consolidation)
        assert currency.gold == 1
        assert currency.silver == 2

    def test_consolidate_electrum_to_gold(self):
        """Test converting 2+ electrum to gold"""
        currency = Currency(electrum=5)
        currency.consolidate()
        assert currency.gold == 2
        assert currency.electrum == 1

    def test_consolidate_gold_to_platinum(self):
        """Test converting 10+ gold to platinum"""
        currency = Currency(gold=25)
        currency.consolidate()
        assert currency.platinum == 2
        assert currency.gold == 5

    def test_consolidate_all_denominations(self):
        """Test full consolidation from copper to platinum"""
        # 1234 cp = 1 pp + 2 gp + 0 ep + 3 sp + 4 cp (after consolidation)
        # 1000 (pp) + 200 (gp) + 0 (ep) + 30 (sp) + 4 (cp) = 1234
        currency = Currency(copper=1234)
        currency.consolidate()
        assert currency.platinum == 1
        assert currency.gold == 2
        assert currency.electrum == 0
        assert currency.silver == 3
        assert currency.copper == 4
        # Verify total is unchanged
        assert currency.to_copper() == 1234

    def test_consolidate_small_amounts(self):
        """Test that consolidation doesn't affect small amounts"""
        currency = Currency(copper=5, silver=3, electrum=1)
        currency.consolidate()
        assert currency.copper == 5
        assert currency.silver == 3
        assert currency.electrum == 1

    def test_consolidate_is_idempotent(self):
        """Test that consolidating twice gives same result"""
        currency = Currency(copper=1234)
        currency.consolidate()
        state_after_first = (currency.copper, currency.silver, currency.electrum, currency.gold, currency.platinum)
        currency.consolidate()
        state_after_second = (currency.copper, currency.silver, currency.electrum, currency.gold, currency.platinum)
        assert state_after_first == state_after_second


class TestCurrencyComparison:
    """Test comparison operators"""

    def test_equality(self):
        """Test equality comparison"""
        c1 = Currency(gold=5, silver=3)
        c2 = Currency(gold=5, silver=3)
        c3 = Currency(gold=5, silver=2)
        assert c1 == c2
        assert not (c1 == c3)

    def test_equality_with_non_currency(self):
        """Test equality with non-Currency returns NotImplemented"""
        c1 = Currency(gold=5)
        assert c1.__eq__(5) == NotImplemented

    def test_equality_ignores_denomination(self):
        """Test that equality compares values, not denominations"""
        c1 = Currency(gold=5)
        c2 = Currency(silver=50)
        assert c1 == c2

    def test_less_than(self):
        """Test less than comparison"""
        c1 = Currency(gold=2)
        c2 = Currency(gold=5)
        assert c1 < c2
        assert not (c2 < c1)

    def test_less_than_equal(self):
        """Test less than or equal comparison"""
        c1 = Currency(gold=5)
        c2 = Currency(gold=5)
        c3 = Currency(gold=3)
        assert c1 <= c2
        assert c3 <= c1
        assert not (c1 <= c3)

    def test_greater_than(self):
        """Test greater than comparison"""
        c1 = Currency(gold=5)
        c2 = Currency(gold=2)
        assert c1 > c2
        assert not (c2 > c1)

    def test_greater_than_equal(self):
        """Test greater than or equal comparison"""
        c1 = Currency(gold=5)
        c2 = Currency(gold=5)
        c3 = Currency(gold=7)
        assert c1 >= c2
        assert c3 >= c1
        assert not (c1 >= c3)



class TestCurrencyDisplay:
    """Test string representation"""

    def test_str_empty(self):
        """Test string representation of empty currency"""
        currency = Currency()
        assert str(currency) == "0 cp"

    def test_str_single_denomination(self):
        """Test string with single denomination"""
        assert str(Currency(copper=5)) == "5 cp"
        assert str(Currency(silver=3)) == "3 sp"
        assert str(Currency(gold=1)) == "1 gp"
        assert str(Currency(platinum=2)) == "2 pp"

    def test_str_multiple_denominations(self):
        """Test string with multiple denominations"""
        currency = Currency(platinum=1, gold=5, silver=3, copper=7)
        result = str(currency)
        assert "1 pp" in result
        assert "5 gp" in result
        assert "3 sp" in result
        assert "7 cp" in result
        # Should not include 0 ep
        assert "ep" not in result

    def test_str_no_zeros(self):
        """Test that zero denominations are not displayed"""
        currency = Currency(gold=5, platinum=1)
        result = str(currency)
        assert "1 pp" in result
        assert "5 gp" in result
        assert "sp" not in result
        assert "ep" not in result
        assert "cp" not in result

    def test_str_realistic_example(self):
        """Test realistic currency display examples"""
        # Adventurer with mixed currency
        currency = Currency(platinum=1, gold=5, silver=7, copper=3)
        expected = "1 pp, 5 gp, 7 sp, 3 cp"
        assert str(currency) == expected

        # Another realistic example
        currency = Currency(gold=10, copper=42)
        expected = "10 gp, 42 cp"
        assert str(currency) == expected


class TestCurrencyComplexScenarios:
    """Test complex real-world scenarios"""

    def test_merchant_transaction_exact_change(self):
        """Test merchant transaction with exact change"""
        # Player has 15 gp total in mixed denominations
        player = Currency(gold=1, electrum=3)  # 1 gp + 150 cp = 250 cp
        # Merchant charges 150 cp (1.5 gp)
        cost = Currency(gold=1, silver=5)  # 100 cp + 50 cp = 150 cp

        assert player.can_afford(cost)
        result = player.subtract(cost)
        assert result is True
        # Remaining: 250 - 150 = 100 cp (consolidated form = 1 gp)
        assert player.to_copper() == 100
        assert player.gold == 1

    def test_merchant_transaction_with_change_making(self):
        """Test merchant transaction that requires making change"""
        # Player has 1 platinum piece (1000 cp)
        player = Currency(platinum=1)
        # Merchant charges 250 cp
        cost = Currency(gold=2, silver=5)  # 200 cp + 50 cp = 250 cp

        assert player.can_afford(cost)
        result = player.subtract(cost)
        assert result is True
        # Remaining: 1000 - 250 = 750 cp (consolidated form)
        assert player.to_copper() == 750
        # 750 cp = 7 gp (700) + 1 ep (50) + 0 sp + 0 cp (remaining = 0)
        assert player.gold == 7
        assert player.electrum == 1

    def test_treasure_collection_with_consolidation(self):
        """Test collecting treasure and consolidating"""
        # Start empty
        player = Currency()

        # Find 500 cp worth of copper pieces
        player.add(Currency(copper=500))
        # Find 100 cp worth of silver pieces (10 sp)
        player.add(Currency(silver=10))
        # Find 200 cp worth of electrum (4 ep)
        player.add(Currency(electrum=4))

        # Total: 500 + 100 + 200 = 800 cp
        assert player.to_copper() == 800

        # Before consolidation, we have scattered denominations
        assert player.copper == 500
        assert player.silver == 10
        assert player.electrum == 4

        # Consolidate
        player.consolidate()

        # After consolidation: 8 gp + 0 ep + 0 sp + 0 cp
        assert player.to_copper() == 800
        # It should be consolidated to 8 gp
        assert player.gold == 8

    def test_party_treasury(self):
        """Test managing party treasury"""
        party_treasury = Currency()

        # Party defeats three goblin groups
        goblin1_loot = Currency(copper=15, silver=3)
        goblin2_loot = Currency(gold=1, copper=25)
        goblin3_loot = Currency(silver=5, copper=10)

        party_treasury.add(goblin1_loot)
        party_treasury.add(goblin2_loot)
        party_treasury.add(goblin3_loot)

        # Total: 15 + 30 + 25 + 100 + 50 + 10 = 230 cp
        assert party_treasury.to_copper() == 230

        # Party wants to distribute equal shares (4 members)
        # 230 / 4 = 57 cp each with 2 cp remainder
        per_member_cp = party_treasury.to_copper() // 4  # 57 cp each

        # Each member gets 57 cp
        for i in range(4):
            member_share = Currency(silver=5, copper=7)  # 57 cp
            assert party_treasury.can_afford(member_share), f"Failed at iteration {i}"
            party_treasury.subtract(member_share)

        # Treasury should have 2 cp remaining (230 - 228)
        # Result is consolidated form: 2 cp
        assert party_treasury.to_copper() == 2
        assert party_treasury.copper == 2

    def test_insufficient_funds_transaction(self):
        """Test transaction when insufficient funds"""
        player = Currency(gold=2)  # 200 cp
        cost = Currency(gold=5)  # 500 cp

        assert not player.can_afford(cost)
        result = player.subtract(cost)
        assert result is False
        assert player.gold == 2  # Unchanged

    def test_change_making_with_low_denomination(self):
        """Test making change when mostly high denomination available"""
        # Player has 1 platinum piece
        player = Currency(platinum=1)
        # Need to pay 1 copper piece
        cost = Currency(copper=1)

        assert player.can_afford(cost)
        result = player.subtract(cost)
        assert result is True
        # Remaining: 1000 - 1 = 999 cp (consolidated form)
        assert player.to_copper() == 999
        # 999 cp = 9 gp (900) + 1 ep (50) + 4 sp (40) + 9 cp
        assert player.gold == 9
        assert player.electrum == 1
        assert player.silver == 4
        assert player.copper == 9
