"""Human-readable alerts; internal identifiers stay in the journal."""
def format_arbitrage(arb):
    market={'h2h':'Moneyline','spreads':'Spread','totals':'Total'}.get(arb.get('market'),arb.get('market','').replace('player_','').replace('_',' ').title())
    legs=[]
    for leg in arb.get('legs',[]):
        line='' if leg.get('line') is None else f" {leg['line']:+g}" if arb.get('market')=='spreads' else f" {leg['line']:g}"
        legs.append(f"{leg['side']}{line} {leg['american']:+g} at {leg['book']} (${leg['stake_per_100']:.2f} per $100 total)")
    return (f"GOING {arb.get('sport','nfl').upper()} displayed-price arbitrage candidate: "
            f"{arb.get('away','Unknown away team')} at {arb.get('home','Unknown home team')} | "
            f"{arb.get('player') or ''} {market} | {' / '.join(legs)} | "
            f"quoted return {arb['return_if_executable']*100:.1f}%. "
            "Both opposing bets must be accepted at these prices and stake amounts. Limits and matching void rules still need checking."
            + (' NCAA availability not independently verified.' if arb.get('sport')=='ncaa' else ''))
