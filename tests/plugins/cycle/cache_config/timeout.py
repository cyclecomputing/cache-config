import time

def get(request, response):
    time.sleep(30)
    response.write("Timeout success", "text/plain")
