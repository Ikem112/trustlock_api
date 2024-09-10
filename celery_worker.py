from project.api_services.sendgrid_api import celery

if __name__ == "__main__":
    celery.start()
