import datetime
import time
time1 = datetime.datetime.now()
time.sleep(200)
time2 = datetime.datetime.now() # waited a few minutes before pressing enter
elapsedTime = time2 - time1

print("<>>>",elapsedTime.total_seconds())

# divmod returns quotient and remainder
# 2 minutes, 5.74943 seconds