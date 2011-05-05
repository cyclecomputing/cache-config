from app import logger

# Handle GET requests
def get(request, response):
    logger.info("Handling request")
    
    import time
    #    time.sleepBAD(10)
    response.setStatus(202)
    response.write("Success\n", "text/plain")
