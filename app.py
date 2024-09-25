from project import create_app, scheduler
from project.api_services.paystack_api import PaystackClient


app = create_app()


from project.jobs import check_inspection_dates

with app.app_context():

    def start_scheduler():
        scheduler.add_job(
            func=check_inspection_dates, trigger="interval", hours=1, id="myCheckJob"
        )
        if not scheduler.running:
            scheduler.start()
        print("scheduler is running")
        return "scheduler has started"


@app.teardown_appcontext
def shutdown_scheduler(exception=None):
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.shell_context_processor
def make_shell_context():
    return dict(PaystackClient=PaystackClient)


if __name__ == "__main__":
    start_scheduler()
    app.run(host="0.0.0.0", port=80)
