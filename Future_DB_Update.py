import logging
from datetime import datetime, timedelta
import pytz
from Tables.Orders_Pull_Update import run_order_update

def get_va_time():
    """Returns the current time in Virginia."""
    va_tz = pytz.timezone('US/Eastern')
    return datetime.now(va_tz)

def day_lookup(today_weekday):
# 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    today_weekday = today_weekday.weekday()
    if today_weekday == 0:
        look_ahead = 14
    elif today_weekday == 1:
        look_ahead = 14
    elif today_weekday == 2:
        look_ahead = 14
    elif today_weekday == 3:
        look_ahead = 14
    elif today_weekday == 4:
        look_ahead = 14
    else:                     # Standard: Just pull tomorrow
        look_ahead = 14
    return look_ahead

def main():
    va_now = get_va_time()
    num_days = day_lookup(va_now)

    # 1. Handle API Syncs first
    for i in range(1, num_days + 1):
        target_str = (va_now + timedelta(days=i)).strftime('%Y%m%d')
        run_order_update(target_date=target_str)

if __name__ == "__main__":
    main()