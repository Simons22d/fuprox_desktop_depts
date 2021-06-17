from fuprox import app
import eventlet.wsgi

# import multiprocessing
# multiprocessing function
# caller

if __name__ == "__main__":
    eventlet.wsgi.server(eventlet.listen(("", 1000)), app)
    # app.run("0.0.0.0", port=1000, debug=True)
