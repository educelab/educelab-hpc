from datetime import timedelta as td

def timedelta_str(delta: td):
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    mins, secs = divmod(rem, 60)
    has_days = days > 0
    has_hours = has_days or hours > 0
    has_mins = has_hours or mins > 0

    dur_str = f'{secs}s'
    dur_str = f'{mins}m{dur_str}' if has_mins else dur_str
    dur_str = f'{hours}h{dur_str}' if has_hours else dur_str
    dur_str = f'{days}d{dur_str}' if has_days else dur_str
    return dur_str