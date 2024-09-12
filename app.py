from project import create_app
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

app = create_app()
scheduler = BackgroundScheduler()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
