from comparison.queries import (
    get_block_intervals, get_finality_lag_series, get_missed_slot_stats,
    get_time_to_inclusion, get_confirmation_milestone_times, get_reorg_events,
    get_gas_utilization_series
)

start = '2020-01-01T00:00:00+00:00'
end = '2030-01-01T00:00:00+00:00'

for name, db in [('MAINNET', 'databases/mainnet.db'), ('TESTNET', 'databases/testnet.db')]:
    print(f'=== {name} ===')
    intervals = get_block_intervals(db, start, end)
    print('block_intervals: n=%d sample=%s' % (len(intervals), intervals[:3]))

    lag = get_finality_lag_series(db, start, end)
    print('finality_lag_series: n=%d sample=%s' % (len(lag), lag[:2]))

    missed = get_missed_slot_stats(db, start, end)
    print('missed_slot_stats:', missed)

    inclusion = get_time_to_inclusion(db, start, end)
    print('time_to_inclusion: n=%d sample=%s' % (len(inclusion), inclusion[:3]))

    milestones = get_confirmation_milestone_times(db, start, end)
    print('confirmation_milestones:', {k: len(v) for k, v in milestones.items()})

    reorgs = get_reorg_events(db, start, end)
    print('reorg_events: n=%d sample=%s' % (len(reorgs), reorgs[:2]))

    gas = get_gas_utilization_series(db, start, end)
    print('gas_utilization: n=%d sample=%s' % (len(gas), gas[:2]))
    print()