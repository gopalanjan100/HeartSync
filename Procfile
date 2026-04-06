web: python manage.py migrate && python manage.py collectstatic --noinput && python manage.py create_superuser_if_none && gunicorn heartsync.wsgi --bind 0.0.0.0:$PORT --log-file -
