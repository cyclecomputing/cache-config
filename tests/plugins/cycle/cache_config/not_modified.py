import time

def get(request, response):
    
    type = request.attribute("type")

    reqTime = request.dateHeader("If-Modified-Since")

    # pretend it was modified 5 seconds ago
    modTime = time.time()
    if type == "stale":
        # pretend it was just modified
        modTime = modTime - 1
    else:
        # pretend it was modified over a minute ago
        modTime = modTime - 62

    if reqTime < modTime:
        # the client's copy is out of date
        response.setDateHeader("Last-Modified", modTime)   
        response.write("Downloaded copy")
    else:
        response.setStatus(304)

