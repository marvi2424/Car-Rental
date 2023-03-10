import datetime
from functools import wraps
from dateutil.relativedelta import relativedelta
import time
import stripe
import app as app

date_limits = {
    "max_p": datetime.date.today() + relativedelta(months=+1, days=+1),
    "min_p": datetime.date.today() + relativedelta(days=+1),
    "max_r": datetime.date.today() + relativedelta(months=+1, days=+2),
    "min_r": datetime.date.today() + relativedelta(days=+2),
}


def compare_dates(date1, date2):

    # Split date from yyyy-mm-dd

    if type(date1) == str:
        x = date1.split("-")
        year = int(x[0])
        month = int(x[1])
        day = int(x[2])
        date1 = datetime.date(year, month, day)

    x = date2.split("-")
    year = int(x[0])
    month = int(x[1])
    day = int(x[2])

    # Convert

    date2 = datetime.date(year, month, day)

    if date1 > date2:
        return 0
    elif date1 < date2:
        return 1
    else:
        return 2


# Convert date from yyyy-mm-dd to yyyymmdd


def strdate(date):
    # Split date from yyyy-mm-dd
    x = date.split("-")
    year = x[0]
    month = x[1]
    day = x[2]

    return year + month + day


# Convert from yyyymmdd to dd/mm/yyyy


def strdate_to_d(date):
    year = date[0:4]
    month = date[4:6]
    day = date[6:8]

    return day + "/" + month + "/" + year


def euro(value):
    """Format value as Euro."""
    return f"€{value:,.2f}"


def total_Days(pickupdate, releasedate):

    # Split date (yyyy-mm-dd)
    x = pickupdate.split("-")
    pickup_year = int(x[0])
    pickup_month = int(x[1])
    pickup_day = int(x[2])

    x = releasedate.split("-")
    release_year = int(x[0])
    release_month = int(x[1])
    release_day = int(x[2])

    # Calculate days
    d0 = datetime.date(pickup_year, pickup_month, pickup_day)
    d1 = datetime.date(release_year, release_month, release_day)
    total_days = (d1 - d0).days

    return total_days


# Check if string is date in yyyy-mm-dd format


def is_date(string):

    try:
        datetime.datetime.strptime(string, "%Y-%m-%d")
        return True
    except ValueError:
        return False
