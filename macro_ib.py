from ib_insync import IB, EconomicIndicator
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# רשימת פרסומים מתוזמנים מראש
macro_schedule = [
    {
        'name': 'CPI',
        'conId': 12087792,  # לדוגמה: CPI ארה"ב
        'time': datetime(2025, 8, 19, 15, 30),
        'alerted': False,
        'published': False
    },
    # אפשר להוסיף נתונים נוספים כאן
]

def check_macro_alerts(now=None):
    now = now or datetime.now()
    for event in macro_schedule:
        delta = event['time'] - now
        if timedelta(minutes=0) < delta <= timedelta(minutes=5) and not event['alerted']:
            logger.info(f"⏰ התראה: נתון {event['name']} יתפרסם בעוד 5 דקות ({event['time'].strftime('%H:%M')})")
            event['alerted'] = True

def fetch_macro_data(ib: IB, now=None):
    now = now or datetime.now()
    for event in macro_schedule:
        if abs((event['time'] - now).total_seconds()) < 60 and not event['published']:
            contract = EconomicIndicator(conId=event['conId'])
            tick = ib.reqMktData(contract, snapshot=True)
            ib.sleep(1)
            logger.info(f"📊 נתון {event['name']} פורסם: {tick.last}")
            event['published'] = True