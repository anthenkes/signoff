# Running Celery

=== "Worker"
    ```bash
    celery -A src.celery_app worker -l info
    ```

=== "Beat"
    ```bash
    celery -A src.celery_app beat -l info
    ```

