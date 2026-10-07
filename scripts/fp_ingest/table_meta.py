"""Hand-written facts about each Fantasy Points table GOING has seen. Column lists and signatures are NOT written here:
they are read from the real exports by ``registry.seed`` so the files stay the source of truth."""

TABLES = {
    'efficiency': dict(
        label='Efficiency (rushing, receiving, total, expected fantasy points)', level='player', side='offense', hints=['efficiency'],
        description='Per-player rushing and receiving efficiency plus XFP/XTD expectation; season to date.'),
    'offense_snaps': dict(
        label='Offensive snaps (total, rushing, passing, inside 5/10/20)', level='player', side='offense', hints=['offensesnaps', 'offense snaps'],
        description='Snap counts and snap share with goal-line and red-zone splits.'),
    'passing_advanced': dict(
        label='Passing advanced (QB)', level='player', side='offense', hints=['passingadvanced'],
        description='QB accuracy, pressure, time-to-throw, depth and fantasy production.'),
    'passing_depth': dict(
        label='Passing by depth (QB)', level='player', side='offense', hints=['passingdepth'],
        description='QB attempts, completions, yards and rate by depth bucket.'),
    'qb_coverage_matchup': dict(
        label='QB vs coverage matchup (next game)', level='player', side='matchup', forward_looking=True, hints=['qbcoveragematchup'],
        description='QB production against each coverage family and the next opponent defence mix (OPP is the upcoming opponent).'),
    'wr_coverage_matchup': dict(
        label='Receiver vs coverage matchup (next game)', level='player', side='matchup', forward_looking=True, hints=['wrcoveragematchup'],
        description='Receiver production against each coverage family and the next opponent defence mix (OPP is the upcoming opponent).'),
    'line_matchups': dict(
        label='Offensive line vs defensive front matchups (next game)', level='team', side='matchup', forward_looking=True, hints=['linematchups'],
        description='Team rush/pass grades, pressure and run-block metrics paired with the next opponent defence (teams on bye are absent).'),
    'receiving_advanced': dict(
        label='Receiving advanced', level='player', side='offense', hints=['receivingadvanced'],
        description='Route share, targets, air yards, first-read, designed targets, alignment route split, expected fantasy points.'),
    'receiving_routes_run': dict(
        label='Routes run by alignment', level='player', side='offense', hints=['receivingroutesrun', 'routesrun'],
        description='Routes, targets and per-route production split by wide/slot/inline/backfield.'),
    'receiving_man_vs_zone': dict(
        label='Receiving: man vs zone, single-high vs two-high', level='player', side='offense', hints=['receivingmanvszone'],
        description='Per-route production against man, zone, single-high and two-high shells.'),
    'receiving_separation_by_alignment': dict(
        label='Separation by alignment', level='player', side='offense', hints=['receivingseparationbyalignment'],
        description='Separation score and win rate overall and from wide/slot/inline/backfield.'),
    'receiving_separation_by_breaks': dict(
        label='Separation by route break type', level='player', side='offense', hints=['receivingseparationbybreaks'],
        description='Separation score and win rate by horizontal/vertical/static/shallow route breaks.'),
    'receiving_separation_by_coverage': dict(
        label='Separation by coverage', level='player', side='offense', hints=['receivingseparationbycoverage'],
        description='Separation score and win rate against man, zone, red zone and Cover 2/3/4/6.'),
    'receiving_separation_by_routes': dict(
        label='Separation by route type', level='player', side='offense', hints=['receivingseparationbyroutes'],
        description='Separation, route share and win rate by route tree (slant, out, dig, hitch, comeback, corner, post, go, ...).'),
    'rushing_advanced': dict(
        label='Rushing advanced', level='player', side='offense', hints=['rushingadvanced'],
        description='Explosive/success/stuff rates, yards before/after contact, zone vs man/gap concept splits, expected fantasy points.'),
    'rushing_bell_cow': dict(
        label='Backfield opportunity share (bell cow)', level='player', side='offense', hints=['rushingbellcow'],
        description='Player share of team snaps, rushes, routes, targets and expected fantasy points.'),
    'run_pass_report': dict(
        label='Team run/pass report by situation', level='team', side='offense', hints=['runpassreport'],
        description='Team snaps, pass and rush counts and rates by half, field position, score state, distance and down.'),
}
