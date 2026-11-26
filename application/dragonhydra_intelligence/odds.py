"""Use the same Decimal engine as the released workstation."""
from dragonhydra.market_signals import implied_probability
from living.market_analysis import calculate_market, price as to_decimal


def analyze_decimal(value):
    """Analyze one quote. Market-level metrics require all outcomes."""
    decimal = to_decimal(value, "decimal")
    return {"decimal": str(decimal), "implied": str(implied_probability(decimal)),
            "category": "MATHEMATICAL CALCULATION"}


__all__ = ["to_decimal", "implied_probability", "analyze_decimal", "calculate_market"]
