web: gunicorn -w 4 -k uvicorn.workers.UvicornWorker CCOIN.main:app
worker: celery -A CCOIN.tasks.social_check worker --loglevel=info
