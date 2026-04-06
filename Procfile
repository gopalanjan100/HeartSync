web: python manage.py migrate && python manage.py collectstatic --noinput && python manage.py createsuperuser --noinput || true && gunicorn heartsync.wsgi --bind 0.0.0.0:$PORT --log-file -
