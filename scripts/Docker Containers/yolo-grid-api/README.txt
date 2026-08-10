uvicorn main:app --host 0.0.0.0 --port 8000Building the Docker image takes a long time & huge space in the disk.

Only build if you need it on multiple systems without breaking any code or (works on my machine) error.

Otherwise, run the 'uvicorn main:app --host 0.0.0.0 --port 8000' command to run the server locally without building
the docker image.